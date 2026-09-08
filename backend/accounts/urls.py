from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminOnlyTestView,
    CandidateOnlyTestView,
    CurrentUserView,
    EmployerOnlyTestView,
    GoogleOAuthView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendVerificationView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
    VerifyEmailView,
)

app_name = "accounts"

urlpatterns = [
    # Core Authentication
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current_user"),

    # Password Reset / Migrated Account Activation
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),

    # Email Verification
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="resend_verification"),

    # Google OAuth & Account Linking
    path("oauth/google/", GoogleOAuthView.as_view(), name="google_oauth"),

    # Role-based permission verification endpoints
    path("test-candidate/", CandidateOnlyTestView.as_view(), name="test_candidate"),
    path("test-employer/", EmployerOnlyTestView.as_view(), name="test_employer"),
    path("test-admin/", AdminOnlyTestView.as_view(), name="test_admin"),
]
