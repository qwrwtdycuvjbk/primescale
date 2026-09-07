from django.urls import path
from .views import CompanyDetailView, CompanyMembersView, CompanyMeView

app_name = "companies"

urlpatterns = [
    path("me/", CompanyMeView.as_view(), name="company_me"),
    path("<uuid:pk>/", CompanyDetailView.as_view(), name="company_detail"),
    path("<uuid:pk>/members/", CompanyMembersView.as_view(), name="company_members"),
]
