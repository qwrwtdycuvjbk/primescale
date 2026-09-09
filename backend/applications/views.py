"""
Views for Job Applications.
Phase 17 — Job Applications Migration.

Supports:
- Candidates applying to active jobs
- Candidates listing their own applications
- Employers listing and reviewing applications for their jobs
- Admins listing and filtering applications
- Strict IDOR object-level permissions
- Server-side status transition validation
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from candidates.models import CandidateProfile
from handoffs.services import create_mutual_fit_handoff
from jobs.models import Job
from matching.models import Match
from matching.services import (
    combined_match_score,
    compute_experience_score,
    compute_skill_overlap_score,
    notify_recruiters_candidate_interested,
    resolve_match_status,
)
from .serializers import (
    ApplicationSerializer,
    ApplicationStatusUpdateSerializer,
    ApplyToJobSerializer,
)


class ApplicationListView(APIView):
    """
    GET /api/v1/applications/
    List applications filtered by user role:
    - Candidate: sees applications where they are the applicant (status != suggested)
    - Employer: sees applications for their posted jobs / company
    - Admin: sees all applications with optional ?status= and ?job_id= filtering
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_employer = user.role == User.Role.EMPLOYER
        is_candidate = user.role == User.Role.CANDIDATE

        status_param = request.query_params.get("status")
        job_id = request.query_params.get("job_id") or request.query_params.get("job")

        if is_admin:
            queryset = Match.objects.select_related(
                "job", "job__company", "job__posted_by", "candidate_profile", "candidate_profile__user"
            ).exclude(status=Match.Status.SUGGESTED)

            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)

            queryset = queryset.order_by("-updated_at")
            serializer = ApplicationSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_employer:
            queryset = Match.objects.select_related(
                "job", "candidate_profile", "candidate_profile__user"
            ).filter(
                Q(job__posted_by=user) | Q(job__company__owner=user),
                status__in=[
                    Match.Status.CANDIDATE_INTERESTED,
                    Match.Status.EMPLOYER_SHORTLISTED,
                    Match.Status.MUTUAL_FIT,
                    Match.Status.REJECTED,
                ],
                visible_to_employer=True,
            )

            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)

            queryset = queryset.order_by("-updated_at")
            serializer = ApplicationSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_candidate:
            profile = getattr(user, "candidate_profile", None)
            if not profile:
                return Response([], status=status.HTTP_200_OK)

            queryset = Match.objects.select_related(
                "job", "job__company"
            ).filter(
                candidate_profile=profile,
                status__in=[
                    Match.Status.CANDIDATE_INTERESTED,
                    Match.Status.EMPLOYER_SHORTLISTED,
                    Match.Status.MUTUAL_FIT,
                    Match.Status.REJECTED,
                ],
            )

            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)

            queryset = queryset.order_by("-updated_at")
            serializer = ApplicationSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response([], status=status.HTTP_200_OK)


class ApplyView(APIView):
    """
    POST /api/v1/applications/apply/
    or
    POST /api/v1/applications/
    Allows an authenticated candidate to apply to an active job.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != User.Role.CANDIDATE:
            return Response(
                {"error": "Only candidates can apply to jobs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = getattr(user, "candidate_profile", None)
        if not profile:
            return Response(
                {"error": "Candidate profile not found. Please complete your profile before applying."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ApplyToJobSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        job_id = serializer.validated_data["job_id"]
        job = Job.objects.get(id=job_id)

        # Check existing match/application
        existing = Match.objects.filter(candidate_profile=profile, job=job).first()
        if existing:
            if existing.status in [
                Match.Status.CANDIDATE_INTERESTED,
                Match.Status.EMPLOYER_SHORTLISTED,
                Match.Status.MUTUAL_FIT,
            ]:
                return Response(
                    {"error": "You have already applied to this job."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            elif existing.status == Match.Status.REJECTED:
                return Response(
                    {"error": "This application has already been closed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                # Existing was in 'suggested' status -> advance to candidate_interested
                existing.status = Match.Status.CANDIDATE_INTERESTED
                existing.visible_to_employer = True
                existing.save(update_fields=["status", "visible_to_employer", "updated_at"])
                notify_recruiters_candidate_interested(str(existing.id))
                return Response(
                    {"ok": True, "application": ApplicationSerializer(existing).data},
                    status=status.HTTP_200_OK,
                )

        # If no previous match record existed, calculate deterministic match score and create application
        skill_score = compute_skill_overlap_score(profile.skills or [], job.tech_stack or [])
        exp_score = compute_experience_score(profile.experience_level, job.experience_level)
        match_score = combined_match_score(skill_score, exp_score)

        application = Match.objects.create(
            candidate_profile=profile,
            job=job,
            match_score=match_score,
            status=Match.Status.CANDIDATE_INTERESTED,
            visible_to_employer=True,
        )
        notify_recruiters_candidate_interested(str(application.id))

        return Response(
            {"ok": True, "application": ApplicationSerializer(application).data},
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(APIView):
    """
    GET /api/v1/applications/<uuid:pk>/
    PATCH /api/v1/applications/<uuid:pk>/
    Strict object-level authorization (IDOR protection) and status updates.
    """
    permission_classes = [IsAuthenticated]

    def _get_application_and_check_access(self, user, pk):
        application = get_object_or_404(
            Match.objects.select_related(
                "job", "job__company", "job__posted_by", "candidate_profile", "candidate_profile__user"
            ),
            pk=pk,
        )
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_candidate_owner = application.candidate_profile.user == user
        is_employer_owner = (
            application.job.posted_by == user or application.job.company.owner == user
        )

        if not (is_admin or is_candidate_owner or is_employer_owner):
            return application, False
        return application, True

    def get(self, request, pk):
        application, has_access = self._get_application_and_check_access(request.user, pk)
        if not has_access:
            return Response(
                {"error": "You do not have permission to view this application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApplicationSerializer(application)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        application, has_access = self._get_application_and_check_access(request.user, pk)
        if not has_access:
            return Response(
                {"error": "You do not have permission to update this application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ApplicationStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_candidate_owner = application.candidate_profile.user == user
        is_employer_owner = (
            application.job.posted_by == user or application.job.company.owner == user
        )

        requested_status = serializer.validated_data["status"]

        if is_candidate_owner and not is_admin:
            if requested_status not in [Match.Status.REJECTED]:
                return Response(
                    {"error": "Candidate can only withdraw/reject an application."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if is_employer_owner and not is_admin:
            if requested_status not in [Match.Status.EMPLOYER_SHORTLISTED, Match.Status.REJECTED]:
                return Response(
                    {"error": "Employer can only shortlist or reject applications."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        previous_status = application.status
        final_status = resolve_match_status(previous_status, requested_status)

        application.status = final_status
        application.save(update_fields=["status", "updated_at"])

        if final_status == Match.Status.MUTUAL_FIT:
            create_mutual_fit_handoff(str(application.id))

        return Response(
            {"ok": True, "status": final_status, "application": ApplicationSerializer(application).data},
            status=status.HTTP_200_OK,
        )
