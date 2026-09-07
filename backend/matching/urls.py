from django.urls import path
from .views import AdminMatchActionView, MatchDetailView, MatchListView

app_name = "matching"

urlpatterns = [
    path("", MatchListView.as_view(), name="match_list"),
    path("<uuid:pk>/", MatchDetailView.as_view(), name="match_detail"),
    path("<uuid:pk>/admin-action/", AdminMatchActionView.as_view(), name="admin_match_action"),
]
