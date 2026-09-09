from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from .models import HandoffRequest
from .serializers import HandoffRequestSerializer, HandoffStatusUpdateSerializer
from .services import update_handoff_status


class HandoffQueueView(APIView):
    """
    GET /api/v1/handoffs/ -> List handoffs filtered by role and status
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_candidate = user.role == User.Role.CANDIDATE
        is_employer = user.role == User.Role.EMPLOYER

        status_filter = request.query_params.get("status")

        base_queryset = HandoffRequest.objects.select_related(
            "match",
            "match__job",
            "match__job__company",
            "match__job__posted_by",
            "match__candidate_profile",
            "match__candidate_profile__user",
        ).all().order_by("-created_at")

        if is_admin:
            queryset = base_queryset
        elif is_candidate:
            queryset = base_queryset.filter(match__candidate_profile__user=user)
        elif is_employer:
            queryset = base_queryset.filter(
                Q(match__job__posted_by=user) | Q(match__job__company__owner=user)
            )
        else:
            return Response([], status=status.HTTP_200_OK)

        if status_filter and status_filter != "all":
            queryset = queryset.filter(status=status_filter)

        serializer = HandoffRequestSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HandoffDetailView(APIView):
    """
    GET /api/v1/handoffs/<uuid:pk>/ -> Retrieve handoff detail with ownership validation
    PATCH /api/v1/handoffs/<uuid:pk>/ -> Admin-only status/notes update
    """
    permission_classes = [IsAuthenticated]

    def _get_handoff_and_validate_access(self, user, pk):
        handoff = get_object_or_404(
            HandoffRequest.objects.select_related(
                "match",
                "match__job",
                "match__job__company",
                "match__job__posted_by",
                "match__candidate_profile",
                "match__candidate_profile__user",
            ),
            pk=pk,
        )
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        is_candidate_owner = handoff.match.candidate_profile.user == user
        is_employer_owner = (
            handoff.match.job.posted_by == user or handoff.match.job.company.owner == user
        )

        if not (is_admin or is_candidate_owner or is_employer_owner):
            return handoff, False
        return handoff, True

    def get(self, request, pk):
        handoff, has_access = self._get_handoff_and_validate_access(request.user, pk)
        if not has_access:
            return Response(
                {"error": "You do not have permission to view this handoff."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = HandoffRequestSerializer(handoff)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if not is_admin:
            return Response(
                {"error": "Only administrators and recruiters can modify handoff queue items."},
                status=status.HTTP_403_FORBIDDEN,
            )

        handoff = get_object_or_404(HandoffRequest, pk=pk)
        serializer = HandoffStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        updated_handoff = update_handoff_status(
            str(handoff.id),
            status=serializer.validated_data.get("status"),
            notes=serializer.validated_data.get("notes"),
        )
        return Response(
            {"ok": True, "handoff": HandoffRequestSerializer(updated_handoff).data},
            status=status.HTTP_200_OK,
        )
