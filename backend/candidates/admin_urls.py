from django.urls import path
from .views import (
    AdminCandidateBulkImportView,
    AdminCandidateCreateView,
    AdminCandidateDetailView,
    AdminCandidateListView,
    AdminCandidateResumeView,
)

urlpatterns = [
    path("", AdminCandidateListView.as_view(), name="admin_candidate_list"),
    path("import/", AdminCandidateBulkImportView.as_view(), name="admin_candidate_import"),
    path("create/", AdminCandidateCreateView.as_view(), name="admin_candidate_create_alt"),
    path("<uuid:pk>/", AdminCandidateDetailView.as_view(), name="admin_candidate_detail"),
    path("<uuid:pk>/resume/", AdminCandidateResumeView.as_view(), name="admin_candidate_resume_direct"),
]
