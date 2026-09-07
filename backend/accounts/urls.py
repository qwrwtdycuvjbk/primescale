from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminOnlyTestView,
    CandidateOnlyTestView,
    CurrentUserView,
    EmployerOnlyTestView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    # Role-based permission verification endpoints
    path("test-candidate/", CandidateOnlyTestView.as_view(), name="test_candidate"),
    path("test-employer/", EmployerOnlyTestView.as_view(), name="test_employer"),
    path("test-admin/", AdminOnlyTestView.as_view(), name="test_admin"),
]
