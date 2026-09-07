from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.models import User
from accounts.permissions import IsAdmin, IsCandidate, IsCandidateOrAdmin
from .models import CandidateProfile
from .serializers import (
    CandidateProfileInputSerializer,
    CandidateProfileSerializer,
    PublicTalentCardSerializer,
)


class CandidateMeView(APIView):
    """
    GET /api/v1/candidates/me/ -> Retrieve current candidate's profile
    POST /api/v1/candidates/me/ -> Create/update current candidate's profile
    PATCH /api/v1/candidates/me/ -> Partial update of current candidate's profile
    """
    permission_classes = [IsAuthenticated, IsCandidateOrAdmin]

    def get(self, request):
        profile = CandidateProfile.objects.filter(user=request.user).first()
        if not profile:
            return Response(
                {"error": "Candidate profile not found. Please complete onboarding."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CandidateProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CandidateProfileInputSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile = serializer.save()
        return Response(
            {
                "ok": True,
                "candidateProfileId": str(profile.id),
                "profileCompleteness": profile.profile_completeness,
                "profileComplete": profile.profile_complete,
                "profile": CandidateProfileSerializer(profile).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        return self.post(request)


class PublicTalentShowcaseView(APIView):
    """
    GET /api/v1/candidates/public-showcase/ -> Anonymized public talent cards
    """
    permission_classes = [AllowAny]

    def get(self, request):
        limit = int(request.query_params.get("limit", 8))
        limit = min(max(1, limit), 50)

        queryset = (
            CandidateProfile.objects.filter(
                privacy_visibility=CandidateProfile.PrivacyVisibility.PUBLIC,
                profile_complete=True,
                open_to_matching=True,
                availability_status__in=[
                    CandidateProfile.AvailabilityStatus.ACTIVELY_LOOKING,
                    CandidateProfile.AvailabilityStatus.OPEN,
                ],
            )
            .select_related("user")
            .order_by("-updated_at")[:limit]
        )

        serializer = PublicTalentCardSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminCandidateDetailView(APIView):
    """
    GET /api/v1/candidates/<uuid:pk>/ -> Admin candidate inspection
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        profile = get_object_or_404(CandidateProfile.objects.select_related("user"), pk=pk)
        serializer = CandidateProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
