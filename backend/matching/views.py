from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
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
            queryset = queryset.order_by("-match_score", "-created_at")
            serializer = AdminMatchSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_employer:
            queryset = Match.objects.select_related(
                "job", "candidate_profile", "candidate_profile__user"
            ).filter(
                job__posted_by=user,
                visible_to_employer=True,
            )
            if status_param and status_param != "all":
                queryset = queryset.filter(status=status_param)
            if job_id and job_id != "all":
                queryset = queryset.filter(job_id=job_id)
            queryset = queryset.order_by("-match_score", "-created_at")
            serializer = EmployerMatchSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif is_candidate:
            queryset = Match.objects.select_related(
                "job", "job__company"
            ).filter(
                candidate_profile__user=user
            ).order_by("-match_score", "-created_at")
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
        is_candidate_owner = match.candidate_profile.user == user
        is_employer_owner = match.job.posted_by == user or match.job.company.owner == user

        if not (is_admin or is_candidate_owner or is_employer_owner):
            return match, False
        return match, True

    def get(self, request, pk):
        match, has_access = self._get_match_and_validate_access(request.user, pk)
        if not has_access:
            return Response({"error": "You do not have permission to view this match."}, status=status.HTTP_403_FORBIDDEN)

        if request.user.role == User.Role.CANDIDATE:
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

        requested_status = serializer.validated_data["status"]
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
    PATCH /api/v1/matches/<uuid:pk>/admin-action/ -> Admin release gate (approve / reject)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        serializer = AdminMatchActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data["action"]
        if action == "approve":
            match.visible_to_employer = True
        else:
            match.visible_to_employer = False
            match.status = Match.Status.REJECTED

        match.save(update_fields=["visible_to_employer", "status", "updated_at"])
        return Response({"ok": True}, status=status.HTTP_200_OK)
