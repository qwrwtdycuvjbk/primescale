from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .permissions import IsAdmin, IsCandidate, IsEmployer
from .serializers import (
    TokenLogoutSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
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

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class UserLoginView(APIView):
    """
    POST /api/v1/auth/login/
    Authenticates a user via email and password, returning JWT tokens and profile data.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            # Return 401 for authentication credential failure
            return Response(
                {"error": serializer.errors.get("non_field_errors", ["Invalid email or password."])[0]},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


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
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TokenLogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            {"status": "ok", "message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )


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
