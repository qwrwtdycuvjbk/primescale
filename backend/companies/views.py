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
