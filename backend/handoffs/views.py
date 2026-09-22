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
    GET /api/v1/handoffs/ -> List handoffs (Disabled for Admin)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if is_admin:
            return Response({"error": "Handoffs workflow is not available for Admin role."}, status=status.HTTP_403_FORBIDDEN)
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
    GET /api/v1/handoffs/<uuid:pk>/ -> Retrieve handoff details (Disabled for Admin)
    PATCH /api/v1/handoffs/<uuid:pk>/ -> Update handoff status (Disabled for Admin)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if is_admin:
            return Response({"error": "Handoffs workflow is not available for Admin role."}, status=status.HTTP_403_FORBIDDEN)
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
