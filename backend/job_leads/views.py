"""
Views for Job Leads.
Phase 17 — Job Leads API.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from .models import JobLead
from .serializers import JobLeadSerializer


class JobLeadListView(APIView):
    """
    GET /api/v1/job-leads/
    Returns job leads. Only administrators can query the full leads pipeline.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if not is_admin:
            return Response(
                {"error": "Forbidden. Only administrators can view job leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = request.query_params.get("query", "")
        country = request.query_params.get("country", "")

        leads = JobLead.objects.all()
        if query:
            leads = leads.filter(title__icontains=query)
        if country and country != "worldwide":
            leads = leads.filter(country__iexact=country)

        serializer = JobLeadSerializer(leads, many=True)
        return Response(
            {
                "ok": True,
                "count": len(serializer.data),
                "leads": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser
        if not is_admin:
            return Response(
                {"error": "Forbidden. Only administrators can save job leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = JobLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lead = serializer.save()
        return Response(JobLeadSerializer(lead).data, status=status.HTTP_201_CREATED)


class RoleSubmissionCreateView(APIView):
    """
    POST /api/v1/role-submissions/
    Public intake endpoint for employers submitting open roles without prior registration.
    Replaces Supabase role_submissions insert.
    """
    permission_classes = []  # Publicly accessible for lead generation

    def post(self, request):
        from .serializers import RoleSubmissionSerializer

        serializer = RoleSubmissionSerializer(data=request.data)
        if not serializer.is_valid():
            first_err = next(iter(serializer.errors.values()))
            err_msg = first_err[0] if isinstance(first_err, list) else str(first_err)
            return Response(
                {"error": err_msg, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = serializer.save()
        return Response(
            {
                "ok": True,
                "success": True,
                "id": str(submission.id),
                "data": RoleSubmissionSerializer(submission).data,
                "message": "Role submission received successfully.",
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        """
        GET /api/v1/role-submissions/
        Admin-only review of incoming role submissions.
        """
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        is_admin = request.user.role == User.Role.ADMIN or request.user.is_staff or request.user.is_superuser
        if not is_admin:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from .models import RoleSubmission
        from .serializers import RoleSubmissionSerializer

        submissions = RoleSubmission.objects.all()
        serializer = RoleSubmissionSerializer(submissions, many=True)
        return Response(
            {
                "ok": True,
                "count": submissions.count(),
                "submissions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
