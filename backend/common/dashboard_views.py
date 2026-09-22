"""
Admin Dashboard Analytics Views.
Phase 18 — Admin Read-Only Dashboard Analytics & Platform Monitoring.

Provides platform monitoring statistics across candidates, user accounts,
jobs, applications, and matches. Zero handoffs.
"""

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from candidates.models import CandidateProfile
from external_jobs.models import ExternalJob
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
    Returns platform-wide monitoring statistics and preview lists.
    Strictly restricted to Admin users.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        week_start = get_start_of_week()

        # 1. Candidate Statistics
        total_candidates = User.objects.filter(role=User.Role.CANDIDATE).count()
        new_candidates_this_week = User.objects.filter(
            role=User.Role.CANDIDATE, created_at__gte=week_start
        ).count()
        completed_profiles = CandidateProfile.objects.filter(profile_complete=True).count()
        incomplete_profiles = CandidateProfile.objects.filter(profile_complete=False).count()
        candidates_with_resume = CandidateProfile.objects.filter(
            resume_url__isnull=False
        ).exclude(resume_url="").count()
        candidates_without_resume = CandidateProfile.objects.filter(
            Q(resume_url__isnull=True) | Q(resume_url="")
        ).count()
        candidates_available = CandidateProfile.objects.filter(
            availability_status__in=["actively_looking", "open"]
        ).count()
        candidates_open_to_matching = CandidateProfile.objects.filter(
            open_to_matching=True
        ).count()

        # 2. Employer & User Account Statistics
        total_candidate_accounts = total_candidates
        total_employer_accounts = User.objects.filter(role=User.Role.EMPLOYER).count()
        new_employers_this_week = User.objects.filter(
            role=User.Role.EMPLOYER, created_at__gte=week_start
        ).count()

        # 3. Job Statistics
        total_internal_jobs = Job.objects.count()
        active_jobs = Job.objects.filter(status=Job.Status.ACTIVE).count()
        closed_jobs = Job.objects.filter(status=Job.Status.CLOSED).count()
        draft_jobs = Job.objects.filter(status=Job.Status.DRAFT).count()
        try:
            total_external_jobs = ExternalJob.objects.count()
        except Exception:
            total_external_jobs = 0

        # 4. Application Statistics
        total_applications = Match.objects.exclude(status=Match.Status.SUGGESTED).count()
        candidate_applied_count = Match.objects.filter(
            status=Match.Status.CANDIDATE_INTERESTED
        ).count()
        shortlisted_count = Match.objects.filter(
            status=Match.Status.EMPLOYER_SHORTLISTED
        ).count()
        mutual_fit_count = Match.objects.filter(
            status=Match.Status.MUTUAL_FIT
        ).count()
        rejected_applications = Match.objects.filter(
            status=Match.Status.REJECTED
        ).count()

        # 5. Matching Statistics
        total_matches = Match.objects.count()
        high_confidence_matches = Match.objects.filter(
            match_score__gte=MIN_MATCH_SCORE
        ).count()
        pending_matches_count = Match.objects.filter(
            visible_to_employer=False,
            match_score__gte=MIN_MATCH_SCORE,
        ).exclude(status=Match.Status.REJECTED).count()

        # 6. Previews
        # Top matches
        pending_matches_qs = Match.objects.select_related(
            "job", "job__company", "candidate_profile", "candidate_profile__user"
        ).filter(
            match_score__gte=50,
        ).exclude(status=Match.Status.REJECTED).order_by("-match_score")[:5]

        pending_match_previews = [
            {
                "id": str(m.id),
                "matchScore": m.match_score,
                "status": m.status,
                "candidateName": m.candidate_profile.user.full_name or "Candidate",
                "jobTitle": m.job.title,
                "companyName": m.job.company.name if m.job.company else "Company",
            }
            for m in pending_matches_qs
        ]

        # Recent candidates
        recent_candidates_qs = CandidateProfile.objects.select_related("user").order_by("-created_at")[:5]
        recent_candidate_previews = [
            {
                "id": str(cp.id),
                "name": cp.user.full_name or "Candidate",
                "email": cp.user.email,
                "currentTitle": cp.current_title or "—",
                "completeness": cp.profile_completeness or (100 if cp.profile_complete else 0),
                "availability": cp.availability_status,
                "createdAt": cp.created_at.isoformat(),
            }
            for cp in recent_candidates_qs
        ]

        # Active Jobs with No Matches
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
                "companyName": j.company.name if j.company else "Company",
                "postedAt": j.created_at.isoformat(),
            }
            for j in unmatched_jobs_qs[:5]
        ]

        # Incomplete Profiles
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
                # Candidate Stats
                "totalCandidates": total_candidates,
                "completedProfiles": completed_profiles,
                "incompleteProfiles": incomplete_profiles,
                "candidatesWithResume": candidates_with_resume,
                "candidatesWithoutResume": candidates_without_resume,
                "candidatesAvailable": candidates_available,
                "candidatesOpenToMatching": candidates_open_to_matching,
                "newCandidatesThisWeek": new_candidates_this_week,

                # User Activity & Employer Stats
                "totalCandidateAccounts": total_candidate_accounts,
                "totalEmployerAccounts": total_employer_accounts,
                "newEmployersThisWeek": new_employers_this_week,

                # Job Stats
                "totalInternalJobs": total_internal_jobs,
                "activeJobs": active_jobs,
                "closedJobs": closed_jobs,
                "draftJobs": draft_jobs,
                "totalExternalJobs": total_external_jobs,
                "activeJobsWithNoMatches": active_jobs_with_no_matches,

                # Application Stats
                "totalApplications": total_applications,
                "candidateInterested": candidate_applied_count,
                "employerShortlisted": shortlisted_count,
                "mutualFit": mutual_fit_count,
                "rejectedApplications": rejected_applications,

                # Matching Stats
                "totalMatches": total_matches,
                "highConfidenceMatches": high_confidence_matches,
                "pendingMatches": pending_matches_count,

                # Previews
                "pendingMatchPreviews": pending_match_previews,
                "recentCandidatePreviews": recent_candidate_previews,
                "unmatchedJobPreviews": unmatched_job_previews,
                "incompleteProfilePreviews": incomplete_profile_previews,
            },
            status=status.HTTP_200_OK,
        )
