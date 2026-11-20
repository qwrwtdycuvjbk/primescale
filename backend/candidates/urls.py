from django.urls import path
from .views import (
    AdminCandidateBulkImportView,
    AdminCandidateCreateView,
    AdminCandidateDetailView,
    AdminCandidateListView,
    AdminCandidateResumeView,
    CandidateExternalRecommendationsView,
    CandidateExternalRecommendationFeedbackView,
    CandidateMeView,
    CandidateResumeClearView,
    CandidateResumeView,
    PublicTalentShowcaseView,
)

app_name = "candidates"

urlpatterns = [
    path("me/", CandidateMeView.as_view(), name="candidate_me"),
    path("me/resume/", CandidateResumeView.as_view(), name="candidate_resume"),
    path("me/resume/clear/", CandidateResumeClearView.as_view(), name="candidate_resume_clear"),
    path("external-recommendations/", CandidateExternalRecommendationsView.as_view(), name="candidate_external_recommendations"),
    path("external-recommendations/feedback/", CandidateExternalRecommendationFeedbackView.as_view(), name="candidate_external_recommendations_feedback"),
    path("public-showcase/", PublicTalentShowcaseView.as_view(), name="public_showcase"),
    path("admin/", AdminCandidateListView.as_view(), name="admin_candidate_list_alias"),
    path("<uuid:pk>/", AdminCandidateDetailView.as_view(), name="candidate_detail"),
    path("<uuid:pk>/resume/", AdminCandidateResumeView.as_view(), name="admin_candidate_resume"),
]

