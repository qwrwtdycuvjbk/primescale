from django.urls import path
from .views import JobLeadListView, RoleSubmissionCreateView

app_name = "job_leads"

urlpatterns = [
    path("", JobLeadListView.as_view(), name="job_leads_list"),
    path("submissions/", RoleSubmissionCreateView.as_view(), name="role_submissions_list"),
]
