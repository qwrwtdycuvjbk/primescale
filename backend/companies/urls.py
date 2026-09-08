from django.urls import path
from .views import (
    CompanyDetailView,
    CompanyLogoUploadView,
    CompanyMembersView,
    CompanyMeView,
)

app_name = "companies"

urlpatterns = [
    path("me/", CompanyMeView.as_view(), name="company_me"),
    path("me/logo/", CompanyLogoUploadView.as_view(), name="company_me_logo"),
    path("<uuid:pk>/", CompanyDetailView.as_view(), name="company_detail"),
    path("<uuid:pk>/logo/", CompanyLogoUploadView.as_view(), name="company_logo"),
    path("<uuid:pk>/members/", CompanyMembersView.as_view(), name="company_members"),
]
