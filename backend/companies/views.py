from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.conf import settings
from accounts.models import User
from accounts.permissions import IsAdminReadOnly
from .models import Company, CompanyMember
from .serializers import (
    CompanySerializer,
    CompanyPublicSerializer,
    CompanyMemberSerializer,
    CompanyInputSerializer,
    AdminEmployerListSerializer,
    AdminEmployerDetailSerializer,
)
from .utils import is_work_email_domain_verified
from common.storage import (
    ALLOWED_LOGO_TYPES,
    generate_storage_path,
    get_public_storage,
    validate_file_upload,
)


class CompanyListView(APIView):
    """
    GET /api/v1/companies/ -> List companies (public / dropdown view)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        companies = Company.objects.all().order_by("name")
        serializer = CompanyPublicSerializer(companies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CompanyMeView(APIView):
    """
    GET /api/v1/companies/me/ -> Get current authenticated employer's company profile
    POST /api/v1/companies/me/ -> Create or update company profile
    PATCH /api/v1/companies/me/ -> Partial update company profile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            # Check if user is a member of another company
            membership = request.user.company_memberships.select_related("company").first()
            if membership:
                company = membership.company
            else:
                return Response(
                    {"error": "Company profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if request.user.role not in [User.Role.EMPLOYER, User.Role.ADMIN] and not request.user.is_staff:
            return Response(
                {"error": "Only employer accounts can create company profiles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CompanyInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        website = data.get("website") or ""
        domain_verified = is_work_email_domain_verified(request.user.email, website)

        company, created = Company.objects.update_or_create(
            owner=request.user,
            defaults={
                "name": data.get("name"),
                "website": website,
                "size": data.get("size"),
                "country": data.get("country", "US"),
                "logo_url": data.get("logo_url"),
                "description": data.get("description"),
                "hq_city": data.get("hq_city"),
                "industry": data.get("industry"),
                "remote_culture_statement": data.get("remote_culture_statement"),
                "domain_verified": domain_verified,
                "profile_complete": True,
            },
        )

        # Ensure user is registered as company admin member
        CompanyMember.objects.get_or_create(
            company=company,
            user=request.user,
            defaults={"member_role": CompanyMember.MemberRole.ADMIN},
        )

        out_serializer = CompanySerializer(company)
        return Response(
            {
                "ok": True,
                "companyId": str(company.id),
                "domainVerified": company.domain_verified,
                "profileComplete": company.profile_complete,
                "company": out_serializer.data,
            },
            status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED,
        )

    def patch(self, request):
        company = Company.objects.filter(owner=request.user).first()
        if not company:
            membership = request.user.company_memberships.filter(
                member_role__in=[CompanyMember.MemberRole.ADMIN, CompanyMember.MemberRole.RECRUITER]
            ).select_related("company").first()
            if membership:
                company = membership.company
            else:
                return Response(
                    {"error": "Company profile not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyDetailView(APIView):
    """
    GET /api/v1/companies/<uuid:pk>/ -> Public/employer company profile detail
    PATCH /api/v1/companies/<uuid:pk>/ -> Update company profile
    """
    permission_classes = [AllowAny]

    def get(self, request, pk):
        company = get_object_or_404(Company, pk=pk)
        if (
            request.user.is_authenticated
            and (
                company.owner == request.user
                or company.members.filter(user=request.user).exists()
                or request.user.role == User.Role.ADMIN
                or request.user.is_staff
            )
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

        storage_path = generate_storage_path(str(company.id), file_obj.name)
        storage = get_public_storage()
        saved_path = storage.save(storage_path, file_obj)
        public_url = storage.url(saved_path)

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


class AdminEmployerListView(APIView):
    """
    GET /api/v1/admin/employers/ -> List registered employers for Admin Platform Monitor (Read-Only).
    """
    permission_classes = [IsAuthenticated, IsAdminReadOnly]

    def get(self, request):
        from accounts.models import User
        from companies.serializers import AdminEmployerListSerializer
        from django.db.models import Q

        queryset = User.objects.filter(role=User.Role.EMPLOYER).select_related("owned_company").prefetch_related("posted_jobs", "company_memberships__company")

        q = request.query_params.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                Q(full_name__icontains=q)
                | Q(email__icontains=q)
                | Q(owned_company__name__icontains=q)
                | Q(owned_company__hq_city__icontains=q)
                | Q(owned_company__industry__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter == "active":
            queryset = queryset.filter(is_active=True)
        elif status_filter == "inactive":
            queryset = queryset.filter(is_active=False)

        queryset = queryset.order_by("-created_at")

        total_count = queryset.count()
        active_count = queryset.filter(is_active=True).count()
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        paginated_qs = queryset[offset : offset + limit]

        serializer = AdminEmployerListSerializer(paginated_qs, many=True)
        return Response(
            {
                "employers": serializer.data,
                "results": serializer.data,
                "totalCount": total_count,
                "activeCount": active_count,
                "count": total_count,
            },
            status=status.HTTP_200_OK,
        )


class AdminEmployerDetailView(APIView):
    """
    GET /api/v1/admin/employers/<uuid:pk>/ -> View full employer details (Read-Only).
    """
    permission_classes = [IsAuthenticated, IsAdminReadOnly]

    def get(self, request, pk):
        from accounts.models import User
        from companies.serializers import AdminEmployerDetailSerializer
        from django.db.models import Q

        employer = User.objects.filter(Q(id=pk) | Q(owned_company__id=pk), role=User.Role.EMPLOYER).select_related("owned_company").first()
        if not employer:
            comp = Company.objects.filter(id=pk).select_related("owner").first()
            if comp:
                employer = comp.owner
            else:
                return Response(
                    {"error": "Employer not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = AdminEmployerDetailSerializer(employer)
        return Response(serializer.data, status=status.HTTP_200_OK)