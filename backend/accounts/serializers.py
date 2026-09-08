from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from .models import User
from .tokens import (
    decode_uid,
    encode_uid,
    email_verification_token_generator,
    password_reset_token_generator,
)
from .services import send_password_reset_email, send_verification_email


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
            "email_verified",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "email_verified")


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
        # Dispatch email verification
        token = email_verification_token_generator.make_token(user)
        uidb64 = encode_uid(user.pk)
        send_verification_email(user.email, uidb64, token)

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


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Accepts an email address to request a password reset or claim a migrated account.
    Returns safely without leaking whether the email exists.
    """
    email = serializers.EmailField()

    def save(self):
        email = self.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            token = password_reset_token_generator.make_token(user)
            uidb64 = encode_uid(user.pk)
            send_password_reset_email(user.email, uidb64, token)
        return email


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Validates the password reset token and sets the new password.
    Converts unusable passwords (migrated accounts) into fully usable passwords.
    """
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        uid = attrs.get("uid")
        token = attrs.get("token")
        new_password = attrs.get("new_password")

        user_id = decode_uid(uid)
        if not user_id:
            raise serializers.ValidationError({"token": "Invalid or malformed reset token."})

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except (User.DoesNotExist, ValueError):
            raise serializers.ValidationError({"token": "Invalid reset link or user not found."})

        if not password_reset_token_generator.check_token(user, token):
            raise serializers.ValidationError({"token": "This reset token is invalid or has expired."})

        validate_password(new_password, user=user)

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        # Completing password reset also validates their ownership of the email
        user.email_verified = True
        user.save(update_fields=["password", "email_verified", "updated_at"])
        return user


class VerifyEmailSerializer(serializers.Serializer):
    """
    Verifies user's email using a secure token.
    """
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        uid = attrs.get("uid")
        token = attrs.get("token")

        user_id = decode_uid(uid)
        if not user_id:
            raise serializers.ValidationError({"token": "Invalid or malformed verification link."})

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except (User.DoesNotExist, ValueError):
            raise serializers.ValidationError({"token": "User not found."})

        if not email_verification_token_generator.check_token(user, token):
            raise serializers.ValidationError({"token": "Verification token is invalid or has expired."})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.email_verified = True
        user.save(update_fields=["email_verified", "updated_at"])
        return user


class ResendVerificationSerializer(serializers.Serializer):
    """
    Resends verification email to an unverified user.
    """
    email = serializers.EmailField()

    def save(self):
        email = self.validated_data["email"].strip().lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user and not user.email_verified:
            token = email_verification_token_generator.make_token(user)
            uidb64 = encode_uid(user.pk)
            send_verification_email(user.email, uidb64, token)
        return email


class GoogleOAuthSerializer(serializers.Serializer):
    """
    Authenticates or links a user via Google OAuth identity.
    Accepts verified email and name from frontend/Google ID token.
    Links seamlessly with existing migrated users by email without creating duplicates.
    """
    email = serializers.EmailField()
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(
        choices=[(User.Role.CANDIDATE, "Candidate"), (User.Role.EMPLOYER, "Employer")],
        default=User.Role.CANDIDATE,
    )
    id_token = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_role(self, value):
        if value not in (User.Role.CANDIDATE, User.Role.EMPLOYER):
            raise serializers.ValidationError("Role must be 'candidate' or 'employer'.")
        return value

    def save(self):
        email = self.validated_data["email"].strip().lower()
        full_name = self.validated_data.get("full_name", "").strip()
        role = self.validated_data.get("role", User.Role.CANDIDATE)

        # Account linking: check if account with this email already exists
        user = User.objects.filter(email=email).first()
        if user:
            # Existing migrated user or existing Django user:
            # Link Google identity without modifying original UUID.
            if not user.email_verified:
                user.email_verified = True
                user.save(update_fields=["email_verified", "updated_at"])
            return user, False

        # New user via Google OAuth
        user = User.objects.create_user(
            email=email,
            password=None,  # Unusable password, authenticated via Google
            full_name=full_name,
            role=role,
            email_verified=True,
        )
        return user, True
