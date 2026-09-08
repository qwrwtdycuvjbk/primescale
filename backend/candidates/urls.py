from django.urls import path
from .views import (
    AdminCandidateDetailView,
    AdminCandidateResumeView,
    CandidateMeView,
    CandidateResumeView,
    PublicTalentShowcaseView,
)

app_name = "candidates"

urlpatterns = [
    path("me/", CandidateMeView.as_view(), name="candidate_me"),
    path("me/resume/", CandidateResumeView.as_view(), name="candidate_resume"),
    path("public-showcase/", PublicTalentShowcaseView.as_view(), name="public_showcase"),
    path("<uuid:pk>/", AdminCandidateDetailView.as_view(), name="candidate_detail"),
    path("<uuid:pk>/resume/", AdminCandidateResumeView.as_view(), name="admin_candidate_resume"),
]
