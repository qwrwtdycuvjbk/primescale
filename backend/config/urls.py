from django.contrib import admin
from django.urls import path, include
from common.dashboard_views import AdminDashboardStatsView
from common.views import health_check
from job_leads.views import RoleSubmissionCreateView

api_v1_patterns = [
    path("health/", health_check, name="health-check"),
    path("admin/dashboard/stats/", AdminDashboardStatsView.as_view(), name="admin_dashboard_stats"),
    path("admin/candidates/", include([
        path("", include("candidates.admin_urls")),
    ])),
    path("auth/", include("accounts.urls", namespace="auth")),
    path("companies/", include("companies.urls", namespace="companies")),
    path("candidates/", include("candidates.urls", namespace="candidates")),
    path("jobs/", include("jobs.urls", namespace="jobs")),
    path("external-jobs/", include("external_jobs.urls", namespace="external_jobs")),
    path("matches/", include("matching.urls", namespace="matching")),
    path("handoffs/", include("handoffs.urls", namespace="handoffs")),
    path("applications/", include("applications.urls", namespace="applications")),
    path("job-leads/", include("job_leads.urls", namespace="job_leads")),
    path("role-submissions/", RoleSubmissionCreateView.as_view(), name="role_submissions"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
]
