"""
Token generators for Phase 11 Authentication flows:
1. Password reset tokens (single-use, time-limited, auto-invalidated upon password change)
2. Email verification tokens (time-limited)
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Generates a secure, time-limited token for email verification.
    Includes the email and email_verified status in the hash generator so that
    once verified, the token is automatically invalidated.
    """
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.email}{user.email_verified}{timestamp}"


password_reset_token_generator = PasswordResetTokenGenerator()
email_verification_token_generator = EmailVerificationTokenGenerator()


def encode_uid(user_id) -> str:
    """Encodes a UUID or string user ID into base64 format for safe URL usage."""
    return urlsafe_base64_encode(force_bytes(str(user_id)))


def decode_uid(uidb64: str) -> str:
    """Decodes a base64 encoded user ID back into a string UUID."""
    try:
        return force_str(urlsafe_base64_decode(uidb64))
    except Exception:
        return ""
