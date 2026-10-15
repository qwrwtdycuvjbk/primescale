from django.urls import path
from .views import (
    EmployerJobPublicDetailView,
    EmployerJobPublicListView,
    JobDetailView,
    JobDuplicateView,
    JobListCreateView,
)

app_name = "jobs"

urlpatterns = [
    path("public/", EmployerJobPublicListView.as_view(), name="job_public_list"),
    path("public/<uuid:pk>/", EmployerJobPublicDetailView.as_view(), name="job_public_detail"),
    path("", JobListCreateView.as_view(), name="job_list_create"),
    path("<uuid:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("<uuid:pk>/duplicate/", JobDuplicateView.as_view(), name="job_duplicate"),
]

