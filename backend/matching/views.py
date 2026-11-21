from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from candidates.utils import check_candidate_profile_complete
from handoffs.services import create_mutual_fit_handoff
from .models import Match
from .serializers import (
    AdminMatchActionSerializer,
    AdminMatchSerializer,
    CandidateMatchSerializer,
    EmployerMatchSerializer,
    MatchStatusUpdateSerializer,
)
from .services import notify_recruiters_candidate_interested, resolve_match_status


class MatchListView(APIView):
    """
    GET /api/v1/matches/ -> Lists matches filtered by role
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_employer = user.role == User.Role.EMPLOYER
        is_candidate = user.role == User.Role.CANDIDATE

        status_param = request.query_params.get("status")
        job_id = request.query_params.get("job") or request.query_params.get("job_id")
        limit_param = request.query_params.get("limit")
        try:
            limit = int(limit_param) if limit_param else 100
            limit = max(1, min(limit, 100))
        except (ValueError, TypeError):
            limit = 100

        if is_admin:
            queryset = Match.objects.select_related(
                "job", "job__company", "job__posted_by", "candidate_profile", "candidate_profile__user"
            ).all()
            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)
            visible = request.query_params.get("visible_to_employer")
            if visible is not None:
                queryset = queryset.filter(visible_to_employer=(visible.lower() == "true"))
            queryset = queryset.order_by("-match_score", "-created_at")[:limit]
            serializer = AdminMatchSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_employer:
            queryset = Match.objects.select_related(
                "job", "job__company", "candidate_profile", "candidate_profile__user"
            ).filter(
                Q(job__posted_by=user) | Q(job__company__owner=user) | Q(job__company__members__user=user),
                visible_to_employer=True,
            ).distinct()
            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)
            queryset = queryset.order_by("-match_score", "-created_at")[:limit]
            serializer = EmployerMatchSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_candidate:
            profile = getattr(user, "candidate_profile", None)
            if not profile or getattr(profile, "profile_completeness", 0) != 100:
                return Response([], status=status.HTTP_200_OK)

            queryset = Match.objects.select_related(
                "job", "job__company"
            ).filter(
                candidate_profile__user=user,
                match_score__gte=70,
                job__status="active",
            ).order_by("-match_score", "-created_at")[:limit]
            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            serializer = CandidateMatchSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response([], status=status.HTTP_200_OK)


class MatchDetailView(APIView):
    """
    GET /api/v1/matches/<uuid:pk>/ -> Retrieve match details
    PATCH /api/v1/matches/<uuid:pk>/ -> Update match status (candidate interest, employer shortlist, reject)
    """
    permission_classes = [IsAuthenticated]

    def _get_match_and_validate_access(self, user, pk):
        match = get_object_or_404(
            Match.objects.select_related(
                "job", "job__company", "job__posted_by", "candidate_profile", "candidate_profile__user"
            ),
            pk=pk,
        )
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if is_admin:
            return match, True

        if user.role == User.Role.CANDIDATE:
            is_candidate_owner = match.candidate_profile.user == user
            if is_candidate_owner and match.match_score >= 70:
                return match, True
            return match, False

        if user.role == User.Role.EMPLOYER:
            is_employer_owner = (
                match.job.posted_by == user
                or match.job.company.owner == user
                or match.job.company.members.filter(user=user).exists()
            )
            # Employers can ONLY access approved matches for their company/job
            if is_employer_owner and match.visible_to_employer:
                return match, True
            return match, False

        return match, False

    def get(self, request, pk):
        match, has_access = self._get_match_and_validate_access(request.user, pk)
        if not has_access:
            return Response({"error": "You do not have permission to view this match."}, status=status.HTTP_403_FORBIDDEN)

        if request.user.role == User.Role.CANDIDATE:
            if getattr(match.candidate_profile, "profile_completeness", 0) != 100:
                return Response({"error": "You do not have permission to view this match."}, status=status.HTTP_403_FORBIDDEN)
            serializer = CandidateMatchSerializer(match)
        elif request.user.role == User.Role.EMPLOYER:
            serializer = EmployerMatchSerializer(match)
        else:
            serializer = AdminMatchSerializer(match)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        match, has_access = self._get_match_and_validate_access(request.user, pk)
        if not has_access:
            return Response({"error": "You do not have permission to update this match."}, status=status.HTTP_403_FORBIDDEN)

        serializer = MatchStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if match.status in [Match.Status.MUTUAL_FIT, Match.Status.REJECTED]:
            return Response({"error": "Match is already closed."}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_candidate_owner = match.candidate_profile.user == user
        is_employer_owner = match.job.posted_by == user or match.job.company.owner == user

        requested_status = serializer.validated_data["status"]
        if not is_admin:
            if is_candidate_owner:
                if requested_status not in [Match.Status.CANDIDATE_INTERESTED, Match.Status.REJECTED]:
                    return Response(
                        {"error": "Candidate can only express interest or reject."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                profile = getattr(user, "candidate_profile", None)
                if not profile or not profile.profile_complete or not check_candidate_profile_complete(profile):
                    return Response(
                        {"error": "Please complete your profile before applying for jobs."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if getattr(profile, "profile_completeness", 0) != 100:
                    return Response(
                        {"error": "Profile must be 100% complete to interact with AI recommendations."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            if is_employer_owner and requested_status not in [Match.Status.EMPLOYER_SHORTLISTED, Match.Status.REJECTED]:
                return Response(
                    {"error": "Employer can only shortlist or reject."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        previous_status = match.status
        final_status = resolve_match_status(previous_status, requested_status)

        match.status = final_status
        match.save(update_fields=["status", "updated_at"])

        if final_status == Match.Status.CANDIDATE_INTERESTED and previous_status != Match.Status.CANDIDATE_INTERESTED:
            notify_recruiters_candidate_interested(str(match.id))

        if final_status == Match.Status.MUTUAL_FIT:
            create_mutual_fit_handoff(str(match.id))

        return Response({"ok": True, "status": final_status}, status=status.HTTP_200_OK)


class AdminMatchActionView(APIView):
    """
    POST/PATCH /api/v1/matches/<uuid:pk>/admin-action/ (DISABLED: Read-Only Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        return Response(
            {"error": "Match modification is not permitted for Read-Only Administrator role."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def patch(self, request, pk):
        return Response(
            {"error": "Match modification is not permitted for Read-Only Administrator role."},
            status=status.HTTP_403_FORBIDDEN,
        )


        action = serializer.validated_data["action"]
        if action == "approve":
            match.visible_to_employer = True
        else:
            match.visible_to_employer = False
            match.status = Match.Status.REJECTED

        match.save(update_fields=["visible_to_employer", "status", "updated_at"])
        return Response({"ok": True}, status=status.HTTP_200_OK)


class AdminFeatureToggleListView(APIView):
    """
    GET /api/v1/admin/features/
    List all system feature toggles with effective state and metadata.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        from django.conf import settings
        from .models import SystemFeatureToggle
        from .services import is_external_job_recommendations_enabled

        env_master = getattr(settings, "ENABLE_EXTERNAL_JOB_RECOMMENDATIONS", False)
        toggles = SystemFeatureToggle.objects.select_related("updated_by").all()

        results = []
        for toggle in toggles:
            effective = (
                is_external_job_recommendations_enabled()
                if toggle.feature_key == "external_job_recommendations"
                else (env_master and toggle.is_enabled)
            )
            results.append({
                "feature_key": toggle.feature_key,
                "name": toggle.name,
                "description": toggle.description,
                "is_enabled": toggle.is_enabled,
                "effective_status": effective,
                "environment_master_switch": env_master,
                "updated_at": toggle.updated_at.isoformat() if toggle.updated_at else None,
                "updated_by": {
                    "id": str(toggle.updated_by.id),
                    "email": toggle.updated_by.email,
                } if toggle.updated_by else None,
            })

        return Response({"features": results}, status=status.HTTP_200_OK)


class AdminFeatureToggleDetailView(APIView):
    """
    GET /api/v1/admin/features/<str:feature_key>/
    PATCH /api/v1/admin/features/<str:feature_key>/
    Retrieve or toggle a specific system feature flag.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, feature_key):
        from django.conf import settings
        from .models import SystemFeatureToggle
        from .services import is_external_job_recommendations_enabled

        toggle = get_object_or_404(SystemFeatureToggle.objects.select_related("updated_by"), feature_key=feature_key)
        env_master = getattr(settings, "ENABLE_EXTERNAL_JOB_RECOMMENDATIONS", False)
        effective = (
            is_external_job_recommendations_enabled()
            if toggle.feature_key == "external_job_recommendations"
            else (env_master and toggle.is_enabled)
        )

        return Response({
            "feature_key": toggle.feature_key,
            "name": toggle.name,
            "description": toggle.description,
            "is_enabled": toggle.is_enabled,
            "effective_status": effective,
            "environment_master_switch": env_master,
            "updated_at": toggle.updated_at.isoformat() if toggle.updated_at else None,
            "updated_by": {
                "id": str(toggle.updated_by.id),
                "email": toggle.updated_by.email,
            } if toggle.updated_by else None,
        }, status=status.HTTP_200_OK)

    def patch(self, request, feature_key):
        from django.conf import settings
        from .services import is_external_job_recommendations_enabled, set_system_feature_toggle

        if "is_enabled" not in request.data:
            return Response(
                {"detail": "Field 'is_enabled' (boolean) is required.", "code": "invalid_payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_val = request.data.get("is_enabled")
        if not isinstance(raw_val, bool):
            if str(raw_val).lower() in ("true", "1"):
                is_enabled = True
            elif str(raw_val).lower() in ("false", "0"):
                is_enabled = False
            else:
                return Response(
                    {"detail": "Value for 'is_enabled' must be a valid boolean.", "code": "invalid_boolean"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            is_enabled = raw_val

        success, toggle = set_system_feature_toggle(
            feature_key=feature_key,
            is_enabled=is_enabled,
            user=request.user,
        )

        if not success or not toggle:
            return Response(
                {"detail": "Failed to update feature toggle.", "code": "update_failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        env_master = getattr(settings, "ENABLE_EXTERNAL_JOB_RECOMMENDATIONS", False)
        effective = (
            is_external_job_recommendations_enabled()
            if toggle.feature_key == "external_job_recommendations"
            else (env_master and toggle.is_enabled)
        )

        return Response({
            "success": True,
            "feature_key": toggle.feature_key,
            "name": toggle.name,
            "description": toggle.description,
            "is_enabled": toggle.is_enabled,
            "effective_status": effective,
            "environment_master_switch": env_master,
            "updated_at": toggle.updated_at.isoformat() if toggle.updated_at else None,
            "updated_by": {
                "id": str(toggle.updated_by.id),
                "email": toggle.updated_by.email,
            } if toggle.updated_by else None,
        }, status=status.HTTP_200_OK)

