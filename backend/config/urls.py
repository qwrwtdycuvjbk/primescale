from django.contrib import admin
from django.urls import path, include
from common.views import health_check

api_v1_patterns = [
    path("health/", health_check, name="health-check"),
    path("auth/", include("accounts.urls", namespace="auth")),
    path("companies/", include("companies.urls", namespace="companies")),
    path("candidates/", include("candidates.urls", namespace="candidates")),
    path("jobs/", include("jobs.urls", namespace="jobs")),
    path("matches/", include("matching.urls", namespace="matching")),
    path("handoffs/", include("handoffs.urls", namespace="handoffs")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
]
