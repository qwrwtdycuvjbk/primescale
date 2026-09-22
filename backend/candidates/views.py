from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
import csv
import io

from accounts.models import User
from accounts.permissions import IsAdmin, IsCandidate, IsCandidateOrAdmin
from .models import CandidateProfile
from .serializers import (
    AdminCandidateListSerializer,
    AdminCreateCandidateSerializer,
    CandidateProfileInputSerializer,
    CandidateProfileSerializer,
    PublicTalentCardSerializer,
)
from .utils import calculate_profile_completeness, is_candidate_profile_complete, parse_skills_list
from matching.services import run_matching_for_candidate
from django.conf import settings
from common.storage import (
    ALLOWED_RESUME_TYPES,
    generate_presigned_download_url,
    generate_storage_path,
    get_private_storage,
    validate_file_upload,
)


def create_single_admin_candidate(data: dict) -> tuple:
    """
    Helper to atomically create a User and CandidateProfile for admin flows.
    Returns (candidate_profile, user, matches_created).
    """
    full_name = (data.get("fullName") or data.get("full_name") or "").strip()
    email = data["email"].strip().lower()
    phone = (data.get("phone") or "").strip() or None
    headline = (data.get("headline") or "").strip()
    current_title = (data.get("currentTitle") or data.get("current_title") or "").strip()
    years_exp = data.get("yearsExperience") if data.get("yearsExperience") is not None else data.get("years_experience")
    if years_exp is not None:
        try:
            years_exp = int(years_exp)
        except (ValueError, TypeError):
            years_exp = None

    raw_skills = data.get("skills", [])
    skills = parse_skills_list(raw_skills)

    role_cats = data.get("roleCategories") or data.get("role_categories") or []
    if isinstance(role_cats, str):
        role_cats = [c.strip() for c in role_cats.split(",") if c.strip()]

    exp_level = (data.get("experienceLevel") or data.get("experience_level") or "mid").strip().lower()
    sal_min = data.get("salaryMin") if data.get("salaryMin") is not None else data.get("salary_min")
    sal_max = data.get("salaryMax") if data.get("salaryMax") is not None else data.get("salary_max")
    work_auth = (data.get("workAuthorization") or data.get("work_authorization") or "international_remote").strip().lower()
    us_state = (data.get("location") or data.get("usState") or data.get("us_state") or "Remote").strip()
    preferred_work = (data.get("preferredWorkType") or data.get("preferred_work_type") or "remote").strip().lower()
    avail_status = (data.get("availabilityStatus") or data.get("availability_status") or "actively_looking").strip().lower()
    privacy = (data.get("privacyVisibility") or data.get("privacy_visibility") or "employers_only").strip().lower()
    bio = (data.get("bio") or "").strip()
    github_url = (data.get("githubUrl") or data.get("github_url") or "").strip()
    portfolio_url = (data.get("portfolioUrl") or data.get("portfolio_url") or "").strip()
    linkedin_url = (data.get("linkedinUrl") or data.get("linkedin_url") or "").strip()
    resume_url = (data.get("resumeUrl") or data.get("resume_url") or "").strip()
    source = (data.get("source") or "people_prime").strip()

    profile_data_dict = {
        "headline": headline,
        "phone": phone,
        "current_title": current_title,
        "years_experience": years_exp,
        "skills": skills,
        "role_categories": role_cats,
        "experience_level": exp_level,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "work_authorization": work_auth,
        "us_state": us_state,
        "preferred_work_type": preferred_work,
        "availability_status": avail_status,
        "privacy_visibility": privacy,
        "bio": bio,
        "github_url": github_url,
        "portfolio_url": portfolio_url,
        "linkedin_url": linkedin_url,
        "resume_url": resume_url,
    }
    completeness = calculate_profile_completeness(profile_data_dict)
    is_complete = is_candidate_profile_complete(profile_data_dict)
    open_to_matching = avail_status != CandidateProfile.AvailabilityStatus.NOT_LOOKING

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            password=None,
            full_name=full_name,
            phone=phone,
            role=User.Role.CANDIDATE,
        )
        user.email_verified = True
        user.save(update_fields=["email_verified"])

        profile = CandidateProfile.objects.create(
            user=user,
            headline=headline,
            phone=phone,
            current_title=current_title,
            years_experience=years_exp,
            skills=skills,
            role_categories=role_cats,
            experience_level=exp_level,
            salary_min=sal_min,
            salary_max=sal_max,
            work_authorization=work_auth,
            us_state=us_state,
            remote_preference="remote" if preferred_work == "remote" else preferred_work,
            preferred_work_type=preferred_work,
            availability_status=avail_status,
            privacy_visibility=privacy,
            bio=bio,
            github_url=github_url or None,
            portfolio_url=portfolio_url or None,
            linkedin_url=linkedin_url or None,
            resume_url=resume_url or None,
            profile_completeness=completeness,
            open_to_matching=open_to_matching,
            profile_complete=is_complete,
            source=source,
        )

    matches_result = {"matched": 0}
    if is_complete and open_to_matching:
        try:
            matches_result = run_matching_for_candidate(str(profile.id))
        except Exception:
            matches_result = {"matched": 0}

    return profile, user, matches_result.get("matched", 0)


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
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

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
    POST /api/v1/candidates/<uuid:pk>/resume/ -> Disabled for Read-Only Admin
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        try:
            profile = CandidateProfile.objects.filter(Q(id=pk) | Q(user_id=pk)).first()
        except Exception:
            profile = None
        if not profile:
            return Response(
                {"error": "Candidate profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not profile.resume_url:
            return Response(
                {"error": "Resume not found for this candidate."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = generate_presigned_download_url(profile.resume_url)
        return Response(
            {
                "ok": True,
                "url": download_url,
                "downloadUrl": download_url,
                "resumePath": profile.resume_url,
                "expires_in": 300,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, pk):
        return Response(
            {"error": "Resume upload is not permitted for Read-Only Administrator role."},
            status=status.HTTP_403_FORBIDDEN,
        )

class AdminCandidateListView(APIView):
    """
    GET /api/v1/admin/candidates/ -> Admin candidate registry with filtering, search, pagination, and KPI counts.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        unattached = User.objects.filter(role=User.Role.CANDIDATE, candidate_profile__isnull=True)
        if unattached.exists():
            for u in unattached:
                CandidateProfile.objects.get_or_create(
                    user=u,
                    defaults={
                        "profile_completeness": 0,
                        "profile_complete": False,
                        "availability_status": "open",
                        "source": "platform",
                    },
                )

        queryset = CandidateProfile.objects.select_related("user").filter(user__role=User.Role.CANDIDATE)

        # Filters
        complete = request.query_params.get("complete")
        if complete == "yes" or complete == "true":
            queryset = queryset.filter(profile_complete=True)
        elif complete == "no" or complete == "false":
            queryset = queryset.filter(profile_complete=False)

        availability = request.query_params.get("availability")
        if availability and availability != "all":
            queryset = queryset.filter(availability_status=availability)

        experience = request.query_params.get("experience")
        if experience and experience != "all":
            queryset = queryset.filter(experience_level=experience)

        work_auth = request.query_params.get("work_auth")
        if work_auth and work_auth != "all":
            queryset = queryset.filter(work_authorization=work_auth)

        matching = request.query_params.get("matching")
        if matching == "yes" or matching == "true":
            queryset = queryset.filter(open_to_matching=True)
        elif matching == "no" or matching == "false":
            queryset = queryset.filter(open_to_matching=False)

        resume = request.query_params.get("resume")
        if resume == "yes":
            queryset = queryset.filter(resume_url__isnull=False).exclude(resume_url="")
        elif resume == "no":
            queryset = queryset.filter(Q(resume_url__isnull=True) | Q(resume_url=""))

        source = request.query_params.get("source")
        if source and source != "all":
            queryset = queryset.filter(source=source)

        # Search filter
        q = request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(user__full_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(headline__icontains=q)
                | Q(current_title__icontains=q)
            )

        # Stable ordering
        queryset = queryset.order_by("-created_at")

        # Aggregate counts for admin dashboard header widgets
        base_qs = CandidateProfile.objects.filter(user__role=User.Role.CANDIDATE)
        total_count = base_qs.count()
        complete_count = base_qs.filter(profile_complete=True).count()
        active_count = base_qs.filter(availability_status=CandidateProfile.AvailabilityStatus.ACTIVELY_LOOKING).count()

        # Pagination
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        paginated_qs = queryset[offset : offset + limit]

        serializer = AdminCandidateListSerializer(paginated_qs, many=True)
        return Response(
            {
                "candidates": serializer.data,
                "results": serializer.data,
                "totalCount": total_count,
                "completeCount": complete_count,
                "activeCount": active_count,
                "count": queryset.count(),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        return AdminCandidateCreateView().post(request)


class AdminCandidateCreateView(APIView):
    """
    POST /api/v1/admin/candidates/create/ -> Admin creates candidate (DISABLED: Read-Only Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {"error": "Candidate creation is not permitted for Read-Only Administrator role."},
            status=status.HTTP_403_FORBIDDEN,
        )

class AdminCandidateBulkImportView(APIView):
    """
    POST /api/v1/admin/candidates/import/ -> Bulk upload candidates (DISABLED: Read-Only Admin).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return Response(
            {"error": "Candidate bulk import is not permitted for Read-Only Administrator role."},
            status=status.HTTP_403_FORBIDDEN,
        )


class AdminCandidateActivateView(APIView):
    """
    POST /api/v1/admin/candidates/<uuid:pk>/activate/
    Activates a candidate account. Only accessible by Admins.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        profile = CandidateProfile.objects.filter(Q(id=pk) | Q(user_id=pk)).select_related("user").first()
        if not profile:
            return Response(
                {"error": "Candidate profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user = profile.user
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            'AUDIT: Admin %s activated candidate account %s (%s)',
            request.user.email,
            user.id,
            user.email,
        )

        return Response(
            {
                "ok": True,
                "message": "Candidate account activated successfully.",
                "is_active": True,
                "candidateId": str(profile.id),
                "userId": str(user.id),
            },
            status=status.HTTP_200_OK,
        )


class AdminCandidateDeactivateView(APIView):
    """
    POST /api/v1/admin/candidates/<uuid:pk>/deactivate/
    Deactivates a candidate account. Only accessible by Admins.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        profile = CandidateProfile.objects.filter(Q(id=pk) | Q(user_id=pk)).select_related("user").first()
        if not profile:
            return Response(
                {"error": "Candidate profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user = profile.user
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            'AUDIT: Admin %s deactivated candidate account %s (%s)',
            request.user.email,
            user.id,
            user.email,
        )

        return Response(
            {
                "ok": True,
                "message": "Candidate account deactivated successfully.",
                "is_active": False,
                "candidateId": str(profile.id),
                "userId": str(user.id),
            },
            status=status.HTTP_200_OK,
        )


class AdminCandidateDeleteView(APIView):
    """
    DELETE /api/v1/admin/candidates/<uuid:pk>/
    Safely deletes a candidate account and related data. Only accessible by Admins.
    """
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk):
        profile = CandidateProfile.objects.filter(Q(id=pk) | Q(user_id=pk)).select_related("user").first()
        if not profile:
            return Response(
                {"error": "Candidate profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user = profile.user
        user_email = user.email
        user_id = str(user.id)

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            'AUDIT: Admin %s deleting candidate account %s (%s)',
            request.user.email,
            user_id,
            user_email,
        )

        user.delete()

        return Response(
            {
                "ok": True,
                "message": "Candidate account deleted successfully.",
                "candidateId": str(pk),
                "userId": user_id,
            },
            status=status.HTTP_200_OK,
        )
