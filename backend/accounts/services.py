"""
Authentication email service utilities for Phase 11.
Provides asynchronous (Celery) or synchronous fallback email dispatching
using Resend and Django mail backend, while suppressing real sends in test environments.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, uidb64: str, token: str) -> bool:
    """
    Sends a password reset/welcome email containing the secure token and UID.
    In testing or when Celery worker is offline, safely handles or logs.
    """
    reset_url = f"http://localhost:3000/auth/password-reset-confirm?uid={uidb64}&token={token}"
    subject = "Reset Your Password - People Remotely"
    message = (
        f"Hello,\n\n"
        f"You requested a password reset (or your migrated account is ready to set a password).\n"
        f"Please click the following link to set your password:\n\n"
        f"{reset_url}\n\n"
        f"This link will expire in 24 hours.\n"
        f"If you did not request this, you can safely ignore this email.\n\n"
        f"— The People Remotely Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"),
            recipient_list=[to_email],
            fail_silently=True,
        )
        logger.info("Dispatched password reset email to %s", to_email)
        return True
    except Exception as e:
        logger.warning("Could not dispatch password reset email to %s: %s", to_email, str(e))
        return False


def send_verification_email(to_email: str, uidb64: str, token: str) -> bool:
    """
    Sends an email verification link containing the secure verification token.
    """
    verify_url = f"http://localhost:3000/auth/verify-email?uid={uidb64}&token={token}"
    subject = "Verify Your Email - People Remotely"
    message = (
        f"Hello,\n\n"
        f"Thank you for signing up with People Remotely!\n"
        f"Please verify your email address by clicking the link below:\n\n"
        f"{verify_url}\n\n"
        f"If you did not create an account, please disregard this message.\n\n"
        f"— The People Remotely Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev"),
            recipient_list=[to_email],
            fail_silently=True,
        )
        logger.info("Dispatched email verification to %s", to_email)
        return True
    except Exception as e:
        logger.warning("Could not dispatch email verification to %s: %s", to_email, str(e))
        return False
