from django.urls import path
from .views import AdminCandidateDetailView, CandidateMeView, PublicTalentShowcaseView

app_name = "candidates"

urlpatterns = [
    path("me/", CandidateMeView.as_view(), name="candidate_me"),
    path("public-showcase/", PublicTalentShowcaseView.as_view(), name="public_showcase"),
    path("<uuid:pk>/", AdminCandidateDetailView.as_view(), name="candidate_detail"),
]
