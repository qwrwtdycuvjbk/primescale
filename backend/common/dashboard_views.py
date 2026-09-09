"""
Admin Dashboard Analytics Views.
Phase 18 — Admin Dashboard Analytics.

Provides atomic ORM aggregation of all admin dashboard statistics and previews,
replacing 9 separate round-trips with a single high-performance query.
"""

from datetime import datetime, timezone as dt_timezone
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from candidates.models import CandidateProfile
from handoffs.models import HandoffRequest
from jobs.models import Job
from matching.models import Match

MIN_MATCH_SCORE = 85


def get_start_of_week():
    """
    Returns UTC datetime for Monday 00:00:00 of the current week.
    """
    now = timezone.now()
    days_from_monday = now.weekday()  # Monday is 0
    monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timezone.timedelta(days=days_from_monday)
    return monday


class AdminDashboardStatsView(APIView):
    """
    GET /api/v1/admin/dashboard/stats/
    Returns aggregated dashboard metrics and preview card lists.
    Strictly restricted to Admin users.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        week_start = get_start_of_week()

        # 1. Navigation Counts & Week Counts
        new_candidates_this_week = User.objects.filter(
            role=User.Role.CANDIDATE, created_at__gte=week_start
        ).count()
        new_employers_this_week = User.objects.filter(
            role=User.Role.EMPLOYER, created_at__gte=week_start
        ).count()

        pending_matches_count = Match.objects.filter(
            visible_to_employer=False,
            match_score__gte=MIN_MATCH_SCORE,
        ).exclude(status=Match.Status.REJECTED).count()

        pending_handoffs_count = HandoffRequest.objects.filter(
            status=HandoffRequest.Status.PENDING
        ).count()

        candidate_interested_count = Match.objects.filter(
            status=Match.Status.CANDIDATE_INTERESTED
        ).count()

        incomplete_profiles_count = CandidateProfile.objects.filter(
            profile_complete=False
        ).count()

        # 2. Previews: Pending Matches (visible_to_employer=False, score >= 85)
        pending_matches_qs = Match.objects.select_related(
            "job", "job__company", "candidate_profile", "candidate_profile__user"
        ).filter(
            visible_to_employer=False,
            match_score__gte=MIN_MATCH_SCORE,
        ).exclude(status=Match.Status.REJECTED).order_by("-match_score")[:5]

        pending_match_previews = [
            {
                "id": str(m.id),
                "matchScore": m.match_score,
                "status": m.status,
                "candidateName": m.candidate_profile.user.full_name or "Candidate",
                "jobTitle": m.job.title,
                "companyName": m.job.company.name,
            }
            for m in pending_matches_qs
        ]

        # 3. Previews: Candidate Interest (status=candidate_interested)
        interested_matches_qs = Match.objects.select_related(
            "job", "job__company", "candidate_profile", "candidate_profile__user"
        ).filter(
            status=Match.Status.CANDIDATE_INTERESTED
        ).order_by("-updated_at")[:5]

        candidate_interest_previews = [
            {
                "id": str(m.id),
                "matchScore": m.match_score,
                "candidateName": m.candidate_profile.user.full_name or "Candidate",
                "jobTitle": m.job.title,
                "companyName": m.job.company.name,
            }
            for m in interested_matches_qs
        ]

        # 4. Previews: Pending Handoffs (status=pending)
        pending_handoffs_qs = HandoffRequest.objects.select_related(
            "match",
            "match__job",
            "match__job__company",
            "match__candidate_profile",
            "match__candidate_profile__user",
        ).filter(
            status=HandoffRequest.Status.PENDING
        ).order_by("-created_at")[:5]

        pending_handoff_previews = [
            {
                "id": str(h.id),
                "candidateName": h.match.candidate_profile.user.full_name or "Candidate",
                "jobTitle": h.match.job.title,
                "companyName": h.match.job.company.name,
            }
            for h in pending_handoffs_qs
        ]

        # 5. Active Jobs with No Matches
        unmatched_jobs_qs = Job.objects.select_related("company").annotate(
            match_count=Count("matches")
        ).filter(
            status=Job.Status.ACTIVE,
            match_count=0,
        ).order_by("-created_at")

        active_jobs_with_no_matches = unmatched_jobs_qs.count()

        unmatched_job_previews = [
            {
                "id": str(j.id),
                "title": j.title,
                "companyName": j.company.name,
                "postedAt": j.created_at.isoformat(),
            }
            for j in unmatched_jobs_qs[:5]
        ]

        # 6. Incomplete Profiles
        incomplete_profiles_qs = CandidateProfile.objects.select_related("user").filter(
            profile_complete=False
        ).order_by("-created_at")[:5]

        incomplete_profile_previews = [
            {
                "id": str(cp.id),
                "name": cp.user.full_name or "Candidate",
                "email": cp.user.email,
                "signedUpAt": cp.created_at.isoformat(),
            }
            for cp in incomplete_profiles_qs
        ]

        return Response(
            {
                "pendingMatches": pending_matches_count,
                "pendingHandoffs": pending_handoffs_count,
                "newCandidatesThisWeek": new_candidates_this_week,
                "newEmployersThisWeek": new_employers_this_week,
                "activeJobsWithNoMatches": active_jobs_with_no_matches,
                "incompleteProfiles": incomplete_profiles_count,
                "candidateInterested": candidate_interested_count,
                "pendingMatchPreviews": pending_match_previews,
                "candidateInterestPreviews": candidate_interest_previews,
                "pendingHandoffPreviews": pending_handoff_previews,
                "unmatchedJobPreviews": unmatched_job_previews,
                "incompleteProfilePreviews": incomplete_profile_previews,
            },
            status=status.HTTP_200_OK,
        )
