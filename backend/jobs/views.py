from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin, IsEmployer, IsEmployerOrAdmin
from companies.models import Company
from companies.utils import is_company_profile_complete
from .models import Job
from .serializers import (
    JobCreateUpdateSerializer,
    JobPublicListSerializer,
    JobSerializer,
)
from .utils import default_job_expiry, parse_skills


class JobListCreateView(APIView):
    """
    GET /api/v1/jobs/ -> List jobs based on role and query parameters
    POST /api/v1/jobs/ -> Create a new job post
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsEmployerOrAdmin()]
        return [AllowAny()]

    def get(self, request):
        user = request.user if request.user.is_authenticated else None
        q = request.query_params.get("q", "").strip()
        experience = request.query_params.get("experience_level") or request.query_params.get("experience")
        role_type = request.query_params.get("role_type")
        work_type = request.query_params.get("work_type")
        status_filter = request.query_params.get("status")
        company_id = request.query_params.get("company_id")

        is_admin = user and (user.role == User.Role.ADMIN or user.is_staff or user.is_superuser)
        is_employer = user and user.role == User.Role.EMPLOYER

        if is_admin:
            queryset = Job.objects.select_related("company", "posted_by").all()
            if status_filter and status_filter != "all":
                queryset = queryset.filter(status=status_filter)
            if company_id:
                queryset = queryset.filter(company_id=company_id)
        elif is_employer and request.query_params.get("view") == "my_company":
            company = Company.objects.filter(owner=user).first()
            if not company:
                return Response([], status=status.HTTP_200_OK)
            queryset = Job.objects.select_related("company", "posted_by").filter(company=company)
            if status_filter and status_filter != "all":
                queryset = queryset.filter(status=status_filter)
        else:
            # Public / Candidate view -> only active, non-expired jobs
            now = timezone.now()
            queryset = (
                Job.objects.select_related("company", "posted_by")
                .filter(status=Job.Status.ACTIVE)
                .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            )

        # Common filters
        if experience and experience != "all":
            queryset = queryset.filter(experience_level=experience)
        if role_type and role_type != "all":
            queryset = queryset.filter(role_type=role_type)
        if work_type and work_type != "all":
            queryset = queryset.filter(work_type=work_type)
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(company__name__icontains=q)
                | Q(description__icontains=q)
            )

        queryset = queryset.order_by("-created_at")

        if is_admin or is_employer:
            serializer = JobSerializer(queryset, many=True)
        else:
            serializer = JobPublicListSerializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = JobCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser

        if is_admin:
            company_id = data.get("company_id")
            if not company_id:
                return Response(
                    {"error": "Admin must specify company_id when posting a job."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            company = get_object_or_404(Company, id=company_id)
        else:
            company = Company.objects.filter(owner=user).first()
            if not company:
                return Response(
                    {"error": "Please complete your company profile before posting a job."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        publish = data.get("publish", False)
        job_status = (
            Job.Status.ACTIVE
            if (publish or data.get("status") == Job.Status.ACTIVE)
            else Job.Status.DRAFT
        )
        expires_at = default_job_expiry() if job_status == Job.Status.ACTIVE else None

        job = Job.objects.create(
            company=company,
            posted_by=user,
            title=data["title"],
            description=data["description"],
            role_type=data["role_type"],
            experience_level=data["experience_level"],
            tech_stack=data.get("tech_stack", []),
            salary_range=data["salary_range"],
            work_type=data.get("work_type", "remote"),
            visa_requirements=data.get("visa_requirements", ""),
            status=job_status,
            expires_at=expires_at,
            jd_quality_score=data.get("jd_quality_score"),
            jd_quality_feedback=data.get("jd_quality_feedback"),
            featured=data.get("featured", False),
        )

        return Response(
            {
                "ok": True,
                "jobId": str(job.id),
                "status": job.status,
                "job": JobSerializer(job).data,
            },
            status=status.HTTP_201_CREATED,
        )


class JobDetailView(APIView):
    """
    GET /api/v1/jobs/<uuid:pk>/ -> Retrieve job
    PATCH /api/v1/jobs/<uuid:pk>/ -> Update job
    DELETE /api/v1/jobs/<uuid:pk>/ -> Delete job
    """

    def get_permissions(self):
        if self.request.method in ["PATCH", "DELETE"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    def _can_modify(self, user, job):
        if not user or not user.is_authenticated:
            return False
        if user.role == User.Role.ADMIN or user.is_staff or user.is_superuser:
            return True
        return job.posted_by == user or job.company.owner == user

    def get(self, request, pk):
        job = get_object_or_404(Job.objects.select_related("company", "posted_by"), pk=pk)
        if self._can_modify(request.user, job):
            serializer = JobSerializer(job)
        else:
            if job.status != Job.Status.ACTIVE:
                return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
            serializer = JobPublicListSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        job = get_object_or_404(Job.objects.select_related("company", "posted_by"), pk=pk)
        if not self._can_modify(request.user, job):
            return Response(
                {"error": "You do not have permission to modify this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get("status")
        if new_status and new_status not in [c[0] for c in Job.Status.choices]:
            return Response({"error": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        # Update allowed fields
        for field in [
            "title",
            "description",
            "role_type",
            "experience_level",
            "salary_range",
            "work_type",
            "visa_requirements",
            "jd_quality_score",
            "jd_quality_feedback",
            "featured",
        ]:
            if field in request.data:
                setattr(job, field, request.data[field])

        if "tech_stack" in request.data:
            job.tech_stack = parse_skills(request.data["tech_stack"])

        if new_status:
            previous_status = job.status
            job.status = new_status
            if new_status == Job.Status.ACTIVE and previous_status != Job.Status.ACTIVE:
                job.expires_at = default_job_expiry()

        job.save()
        return Response(
            {"ok": True, "job": JobSerializer(job).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        if not self._can_modify(request.user, job):
            return Response(
                {"error": "You do not have permission to delete this job."},
                status=status.HTTP_403_FORBIDDEN,
            )
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobDuplicateView(APIView):
    """
    POST /api/v1/jobs/<uuid:pk>/duplicate/ -> Duplicate existing job as draft
    """
    permission_classes = [IsAuthenticated, IsEmployerOrAdmin]

    def post(self, request, pk):
        source = get_object_or_404(Job, pk=pk)
        user = request.user
        is_admin = user.role == User.Role.ADMIN or user.is_staff or user.is_superuser

        if not (is_admin or source.posted_by == user or source.company.owner == user):
            return Response(
                {"error": "You do not have permission to duplicate this job."},
                status=status.HTTP_403_FORBIDDEN,
            )

        copy_job = Job.objects.create(
            company=source.company,
            posted_by=user,
            title=f"{source.title} (copy)",
            description=source.description,
            role_type=source.role_type,
            experience_level=source.experience_level,
            tech_stack=source.tech_stack,
            salary_range=source.salary_range,
            work_type=source.work_type,
            visa_requirements=source.visa_requirements,
            status=Job.Status.DRAFT,
            jd_quality_score=source.jd_quality_score,
            jd_quality_feedback=source.jd_quality_feedback,
            featured=False,
        )

        return Response(
            {
                "ok": True,
                "jobId": str(copy_job.id),
                "job": JobSerializer(copy_job).data,
            },
            status=status.HTTP_201_CREATED,
        )
