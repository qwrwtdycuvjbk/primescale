from django.urls import path
from .views import JobDetailView, JobDuplicateView, JobListCreateView

app_name = "jobs"

urlpatterns = [
    path("", JobListCreateView.as_view(), name="job_list_create"),
    path("<uuid:pk>/", JobDetailView.as_view(), name="job_detail"),
    path("<uuid:pk>/duplicate/", JobDuplicateView.as_view(), name="job_duplicate"),
]
