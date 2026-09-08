from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .cookies import clear_auth_cookies, set_auth_cookies
from .models import User
from .permissions import IsAdmin, IsCandidate, IsEmployer
from .serializers import (
    GoogleOAuthSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ResendVerificationSerializer,
    TokenLogoutSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)


class UserRegistrationView(APIView):
    """
    POST /api/v1/auth/register/
    Registers a new candidate or employer account.
    Admin registration via this endpoint is strictly prohibited.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )
        return set_auth_cookies(response, access_token, refresh_token)


class UserLoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticates a user via email and password, returning JWT tokens and profile data.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors.get("non_field_errors", ["Invalid email or password."])[0]},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        return set_auth_cookies(response, access_token, refresh_token)


class CurrentUserView(APIView):
    """
    GET /api/v1/auth/me/
    Returns the authenticated user's profile details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserLogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Blacklists the provided refresh token, invalidating future refresh attempts.
    Also clears HttpOnly auth cookies.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if not refresh_token:
            serializer = TokenLogoutSerializer(data=request.data)
            serializer.is_valid()
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = TokenLogoutSerializer(data={"refresh": refresh_token})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        response = Response(
            {"status": "ok", "message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )
        return clear_auth_cookies(response)


class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password-reset/
    Requests a password reset / claim email for migrated or existing users.
    Returns 200 without leaking whether the email exists (anti-enumeration).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"detail": "If the email is registered, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password-reset-confirm/
    Sets a new password using a secure token, converting unusable passwords to usable.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response(
            {
                "detail": "Password has been successfully updated. Your account is now active.",
                "access": access_token,
                "refresh": refresh_token,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )
        return set_auth_cookies(response, access_token, refresh_token)


class VerifyEmailView(APIView):
    """
    POST /api/v1/auth/verify-email/
    Confirms the user's email address using a secure verification token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        return Response(
            {"detail": "Email address has been successfully verified.", "user": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class ResendVerificationView(APIView):
    """
    POST /api/v1/auth/resend-verification/
    Resends an email verification link.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"detail": "If the account is unverified, a verification link has been sent."},
            status=status.HTTP_200_OK,
        )


class GoogleOAuthView(APIView):
    """
    POST /api/v1/auth/oauth/google/
    Authenticates via Google OAuth identity.
    Safely links to existing migrated accounts by email without creating duplicates.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleOAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user, created = serializer.save()
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        response = Response(
            {
                "access": access_token,
                "refresh": refresh_token,
                "user": UserSerializer(user).data,
                "created": created,
            },
            status=status_code,
        )
        return set_auth_cookies(response, access_token, refresh_token)


# Role Test Views for Permission Verification
class CandidateOnlyTestView(APIView):
    permission_classes = [IsCandidate]

    def get(self, request):
        return Response({"message": "Candidate access granted", "user_id": str(request.user.id)})


class EmployerOnlyTestView(APIView):
    permission_classes = [IsEmployer]

    def get(self, request):
        return Response({"message": "Employer access granted", "user_id": str(request.user.id)})


class AdminOnlyTestView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response({"message": "Admin access granted", "user_id": str(request.user.id)})
