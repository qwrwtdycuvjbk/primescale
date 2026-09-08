from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.models import User
from accounts.permissions import IsAdmin, IsEmployer, IsEmployerOrAdmin, IsOwnerOrAdmin
from .models import Company, CompanyMember
from .serializers import (
    CompanyInputSerializer,
    CompanyMemberSerializer,
    CompanyPublicSerializer,
    CompanySerializer,
)
from django.conf import settings
from common.storage import (
    ALLOWED_LOGO_TYPES,
    generate_storage_path,
    get_public_storage,
    validate_file_upload,
)


class CompanyMeView(APIView):
    """
    GET /api/v1/companies/me/ -> Retrieve current employer's company
    POST /api/v1/companies/me/ -> Create or update current employer's company
    PATCH /api/v1/companies/me/ -> Partial update of current employer's company
    """
    permission_classes = [IsAuthenticated, IsEmployerOrAdmin]

    def get(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response(
                {"error": "Company profile not found. Please complete onboarding."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if company:
            # Update existing
            serializer = CompanyInputSerializer(
                company, data=request.data, partial=True, context={"request": request}
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            updated = serializer.save()
            return Response(
                {
                    "ok": True,
                    "companyId": str(updated.id),
                    "domainVerified": updated.domain_verified,
                    "profileComplete": updated.profile_complete,
                    "company": CompanySerializer(updated).data,
                },
                status=status.HTTP_200_OK,
            )

        serializer = CompanyInputSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_company = serializer.save()
        return Response(
            {
                "ok": True,
                "companyId": str(new_company.id),
                "domainVerified": new_company.domain_verified,
                "profileComplete": new_company.profile_complete,
                "company": CompanySerializer(new_company).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            return Response(
                {"error": "Company profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CompanyInputSerializer(
            company, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        updated = serializer.save()
        return Response(CompanySerializer(updated).data, status=status.HTTP_200_OK)


class CompanyDetailView(APIView):
    """
    GET /api/v1/companies/<uuid:pk>/ -> Public/Authenticated company view
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        # If requester is owner or staff, return full details; otherwise public
        if request.user.is_authenticated and (
            request.user == company.owner or request.user.is_staff or request.user.role == User.Role.ADMIN
        ):
            serializer = CompanySerializer(company)
        else:
            serializer = CompanyPublicSerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CompanyMembersView(APIView):
    """
    GET /api/v1/companies/<uuid:pk>/members/ -> List members
    POST /api/v1/companies/<uuid:pk>/members/ -> Add a member
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        # Check if user is owner or member or admin
        is_member = company.members.filter(user=request.user).exists()
        is_owner = company.owner == request.user
        is_admin = request.user.role == User.Role.ADMIN or request.user.is_staff

        if not (is_owner or is_member or is_admin):
            return Response(
                {"error": "You do not have access to this company's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        members = company.members.select_related("user").all()
        serializer = CompanyMemberSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        is_owner = company.owner == request.user
        is_admin = request.user.role == User.Role.ADMIN or request.user.is_staff

        if not (is_owner or is_admin):
            return Response(
                {"error": "Only company owners and administrators can add members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = request.data.get("user_id")
        email = request.data.get("email")
        member_role = request.data.get("member_role", CompanyMember.MemberRole.RECRUITER)

        target_user = None
        if user_id:
            target_user = User.objects.filter(id=user_id).first()
        elif email:
            target_user = User.objects.filter(email=email.strip().lower()).first()

        if not target_user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if company.members.filter(user=target_user).exists():
            return Response(
                {"error": "User is already a member of this company."},
                status=status.HTTP_409_CONFLICT,
            )

        member = CompanyMember.objects.create(
            company=company, user=target_user, member_role=member_role
        )
        return Response(CompanyMemberSerializer(member).data, status=status.HTTP_201_CREATED)


class CompanyLogoUploadView(APIView):
    """
    POST /api/v1/companies/me/logo/ -> Upload company logo for current user's company
    POST /api/v1/companies/<uuid:pk>/logo/ -> Upload company logo by company ID
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            company = get_object_or_404(Company, pk=pk)
        else:
            company = Company.objects.filter(owner=request.user).first()
            if not company:
                return Response(
                    {"error": "Company profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Authorization check: owner, admin/recruiter member, or platform admin
        is_owner = company.owner == request.user
        is_admin = request.user.role == User.Role.ADMIN or request.user.is_staff or request.user.is_superuser
        is_company_admin = company.members.filter(
            user=request.user,
            member_role__in=[CompanyMember.MemberRole.ADMIN, CompanyMember.MemberRole.RECRUITER],
        ).exists()

        if not (is_owner or is_admin or is_company_admin):
            return Response(
                {"error": "You do not have permission to manage logos for this company."},
                status=status.HTTP_403_FORBIDDEN,
            )

        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        from rest_framework.exceptions import ValidationError
        try:
            validate_file_upload(
                file_obj,
                allowed_types=ALLOWED_LOGO_TYPES,
                max_size_bytes=settings.MAX_LOGO_SIZE_BYTES,
            )
        except ValidationError as e:
            return Response({"error": str(e.detail[0] if isinstance(e.detail, list) else e.detail)}, status=status.HTTP_400_BAD_REQUEST)

        # Save to public storage
        storage_path = generate_storage_path(str(company.id), file_obj.name)
        storage = get_public_storage()
        saved_path = storage.save(storage_path, file_obj)
        public_url = storage.url(saved_path)

        # Update company record
        company.logo_url = public_url
        company.save(update_fields=["logo_url", "updated_at"])

        return Response(
            {
                "ok": True,
                "url": public_url,
                "logoPath": saved_path,
            },
            status=status.HTTP_200_OK,
        )
