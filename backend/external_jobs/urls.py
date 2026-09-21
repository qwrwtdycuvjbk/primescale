from django.urls import path
from external_jobs.views import ExternalJobListAPIView, ExternalJobDetailAPIView

app_name = "external_jobs"

urlpatterns = [
    path("", ExternalJobListAPIView.as_view(), name="external_job_list"),
    path("<uuid:pk>/", ExternalJobDetailAPIView.as_view(), name="external_job_detail"),
]
