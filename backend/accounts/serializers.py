from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Public/Account user serializer.
    Never exposes passwords, hashes, or sensitive internals.
    """
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone",
            "role",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class UserRegistrationSerializer(serializers.Serializer):
    """
    Serializer for public candidate and employer user registration.
    Admin registration is explicitly forbidden.
    """
    email = serializers.EmailField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default=None)
    role = serializers.ChoiceField(
        choices=[(User.Role.CANDIDATE, "Candidate"), (User.Role.EMPLOYER, "Employer")],
        default=User.Role.CANDIDATE,
    )

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_role(self, value):
        if value not in (User.Role.CANDIDATE, User.Role.EMPLOYER):
            raise serializers.ValidationError("Public registration is only allowed for 'candidate' or 'employer' roles.")
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        password = validated_data["password"]
        full_name = validated_data.get("full_name", "").strip()
        phone = validated_data.get("phone")
        if phone:
            phone = phone.strip()
        role = validated_data.get("role", User.Role.CANDIDATE)

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            role=role,
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for authenticating users via email and password.
    Returns authenticated user object.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password", "")

        if not email or not password:
            raise serializers.ValidationError("Both email and password are required.")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs["user"] = user
        return attrs


class TokenLogoutSerializer(serializers.Serializer):
    """
    Serializer for logging out by blacklisting the provided refresh token.
    """
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs.get("refresh")
        return attrs

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except TokenError as e:
            raise serializers.ValidationError({"refresh": f"Invalid or expired token: {str(e)}"})
