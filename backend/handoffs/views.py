from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from .models import HandoffRequest
from .serializers import HandoffRequestSerializer, HandoffStatusUpdateSerializer
from .services import update_handoff_status


class HandoffQueueView(APIView):
    """
    GET /api/v1/handoffs/ -> Admin-only queue of mutual fit handoffs
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        status_filter = request.query_params.get("status")
        queryset = HandoffRequest.objects.select_related(
            "match",
            "match__job",
            "match__job__company",
            "match__job__posted_by",
            "match__candidate_profile",
            "match__candidate_profile__user",
        ).all().order_by("-created_at")

        if status_filter and status_filter != "all":
            queryset = queryset.filter(status=status_filter)

        serializer = HandoffRequestSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HandoffDetailView(APIView):
    """
    GET /api/v1/handoffs/<uuid:pk>/ -> Admin-only handoff detail
    PATCH /api/v1/handoffs/<uuid:pk>/ -> Admin-only status/notes update
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
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
        serializer = HandoffRequestSerializer(handoff)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
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
