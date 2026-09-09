"""
Celery Background Tasks for Accounts.
Phase 18 — Background Services / Celery Verification.
"""

from celery import shared_task
import logging
from .services import send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email_task(self, to_email: str, uidb64: str, token: str):
    """
    Asynchronous Celery task to send password reset / claim email.
    """
    try:
        success = send_password_reset_email(to_email, uidb64, token)
        logger.info(f"Password reset email task for {to_email} finished: success={success}")
        return success
    except Exception as exc:
        logger.error(f"Error sending password reset email to {to_email}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, to_email: str, uidb64: str, token: str):
    """
    Asynchronous Celery task to send account verification email.
    """
    try:
        success = send_verification_email(to_email, uidb64, token)
        logger.info(f"Verification email task for {to_email} finished: success={success}")
        return success
    except Exception as exc:
        logger.error(f"Error sending verification email to {to_email}: {exc}")
        raise self.retry(exc=exc, countdown=60)
