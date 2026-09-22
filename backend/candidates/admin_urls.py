from django.urls import path
from .views import (
    AdminCandidateActivateView,
    AdminCandidateBulkImportView,
    AdminCandidateCreateView,
    AdminCandidateDeactivateView,
    AdminCandidateDeleteView,
    AdminCandidateDetailView,
    AdminCandidateListView,
    AdminCandidateResumeView,
)

urlpatterns = [
    path("", AdminCandidateListView.as_view(), name="admin_candidate_list"),
    path("import/", AdminCandidateBulkImportView.as_view(), name="admin_candidate_import"),
    path("create/", AdminCandidateCreateView.as_view(), name="admin_candidate_create_alt"),
    path("<uuid:pk>/", AdminCandidateDetailView.as_view(), name="admin_candidate_detail"),
    path("<uuid:pk>/activate/", AdminCandidateActivateView.as_view(), name="admin_candidate_activate"),
    path("<uuid:pk>/deactivate/", AdminCandidateDeactivateView.as_view(), name="admin_candidate_deactivate"),
    path("<uuid:pk>/delete/", AdminCandidateDeleteView.as_view(), name="admin_candidate_delete"),
    path("<uuid:pk>/resume/", AdminCandidateResumeView.as_view(), name="admin_candidate_resume_direct"),
]
