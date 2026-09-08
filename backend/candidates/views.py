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
from django.conf import settings
from common.storage import (
    ALLOWED_RESUME_TYPES,
    generate_presigned_download_url,
    generate_storage_path,
    get_private_storage,
    validate_file_upload,
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


class CandidateResumeView(APIView):
    """
    GET /api/v1/candidates/me/resume/ -> Get temporary presigned download URL for authenticated candidate's resume
    POST /api/v1/candidates/me/resume/ -> Upload candidate resume to private storage
    """
    permission_classes = [IsAuthenticated, IsCandidateOrAdmin]

    def get(self, request):
        profile = CandidateProfile.objects.filter(user=request.user).first()
        if not profile or not profile.resume_url:
            return Response(
                {"error": "Resume not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = generate_presigned_download_url(profile.resume_url)
        return Response(
            {
                "ok": True,
                "downloadUrl": download_url,
                "resumePath": profile.resume_url,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        profile = CandidateProfile.objects.filter(user=request.user).first()
        if not profile:
            return Response(
                {"error": "Candidate profile not found. Please complete profile first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Server-side validation
        from rest_framework.exceptions import ValidationError
        try:
            validate_file_upload(
                file_obj,
                allowed_types=ALLOWED_RESUME_TYPES,
                max_size_bytes=settings.MAX_RESUME_SIZE_BYTES,
            )
        except ValidationError as e:
            return Response({"error": str(e.detail[0] if isinstance(e.detail, list) else e.detail)}, status=status.HTTP_400_BAD_REQUEST)

        # Generate storage path & save
        storage_path = generate_storage_path(str(request.user.id), file_obj.name)
        storage = get_private_storage()
        saved_path = storage.save(storage_path, file_obj)

        # Update candidate profile
        profile.resume_url = saved_path
        profile.save(update_fields=["resume_url", "updated_at"])

        download_url = generate_presigned_download_url(saved_path)

        return Response(
            {
                "ok": True,
                "resumePath": saved_path,
                "downloadUrl": download_url,
            },
            status=status.HTTP_200_OK,
        )


class AdminCandidateResumeView(APIView):
    """
    GET /api/v1/candidates/<uuid:pk>/resume/ -> Get presigned download URL for a candidate's resume (Admin only)
    POST /api/v1/candidates/<uuid:pk>/resume/ -> Upload a candidate's resume (Admin only)
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        profile = get_object_or_404(CandidateProfile, pk=pk)
        if not profile.resume_url:
            return Response(
                {"error": "Resume not found for this candidate."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = generate_presigned_download_url(profile.resume_url)
        return Response(
            {
                "ok": True,
                "downloadUrl": download_url,
                "resumePath": profile.resume_url,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, pk):
        profile = get_object_or_404(CandidateProfile, pk=pk)
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        from rest_framework.exceptions import ValidationError
        try:
            validate_file_upload(
                file_obj,
                allowed_types=ALLOWED_RESUME_TYPES,
                max_size_bytes=settings.MAX_RESUME_SIZE_BYTES,
            )
        except ValidationError as e:
            return Response({"error": str(e.detail[0] if isinstance(e.detail, list) else e.detail)}, status=status.HTTP_400_BAD_REQUEST)

        storage_path = generate_storage_path(str(profile.user_id), file_obj.name)
        storage = get_private_storage()
        saved_path = storage.save(storage_path, file_obj)

        profile.resume_url = saved_path
        profile.save(update_fields=["resume_url", "updated_at"])

        download_url = generate_presigned_download_url(saved_path)

        return Response(
            {
                "ok": True,
                "resumePath": saved_path,
                "downloadUrl": download_url,
            },
            status=status.HTTP_200_OK,
        )
