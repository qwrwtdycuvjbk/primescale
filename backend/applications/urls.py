from django.urls import path
from .views import ApplicationDetailView, ApplicationListView, ApplyView

app_name = "applications"

urlpatterns = [
    path("", ApplicationListView.as_view(), name="application_list"),
    path("apply/", ApplyView.as_view(), name="application_apply"),
    path("<uuid:pk>/", ApplicationDetailView.as_view(), name="application_detail"),
]
