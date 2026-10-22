"""
Resend Webhook Ingestion & Verification Service.

Verifies cryptographic Svix HMAC-SHA256 signatures, deduplicates webhook
events persistently, and executes atomic, safe delivery status transitions
on NotificationOutbox records.
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional, Set

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .client import sanitize_error_message
from .models import DeliveryStatus, NotificationOutbox

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Supported Event Types & Constants
# ---------------------------------------------------------------------------

EVENT_EMAIL_DELIVERED = "email.delivered"
EVENT_EMAIL_BOUNCED = "email.bounced"
EVENT_EMAIL_COMPLAINED = "email.complained"
EVENT_EMAIL_SENT = "email.sent"
EVENT_EMAIL_DELIVERY_DELAYED = "email.delivery_delayed"

SUPPORTED_EVENT_TYPES: Set[str] = {
    EVENT_EMAIL_DELIVERED,
    EVENT_EMAIL_BOUNCED,
    EVENT_EMAIL_COMPLAINED,
    EVENT_EMAIL_SENT,
    EVENT_EMAIL_DELIVERY_DELAYED,
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WebhookVerificationError(Exception):
    """Base exception for webhook signature verification failures."""
    pass


class WebhookSecretNotConfiguredError(WebhookVerificationError):
    """Raised when RESEND_WEBHOOK_SECRET is empty or unconfigured."""
    pass


class WebhookMissingHeadersError(WebhookVerificationError):
    """Raised when one or more required Svix headers are missing."""
    pass


class WebhookExpiredError(WebhookVerificationError):
    """Raised when the webhook timestamp exceeds the allowed replay tolerance."""
    pass


class WebhookInvalidSignatureError(WebhookVerificationError):
    """Raised when the cryptographic signature does not match."""
    pass


class WebhookPayloadError(Exception):
    """Base exception for invalid or malformed webhook payload content."""
    pass


class WebhookUnsupportedEventError(WebhookPayloadError):
    """Raised when the event type is unrecognized or unsupported."""
    pass


class WebhookUnmatchedMessageRetryableError(Exception):
    """
    Raised when a signature-verified webhook references a provider_message_id
    that is not yet committed in the database, but the event is sufficiently fresh
    that it may be racing an in-flight worker database commit.
    """
    def __init__(self, message: str, email_id: str, age_seconds: int):
        super().__init__(message)
        self.email_id = email_id
        self.age_seconds = age_seconds


# ---------------------------------------------------------------------------
# Signature Verification
# ---------------------------------------------------------------------------

def verify_resend_webhook(
    raw_body: bytes,
    headers: Dict[str, str],
    secret: Optional[str] = None,
    tolerance: int = 300,
) -> bool:
    """
    Verifies the Svix HMAC-SHA256 signature according to the official Resend/Svix spec.

    Args:
        raw_body: The unparsed, raw byte stream of the request body.
        headers: Mapping of request headers containing svix-id, svix-timestamp, svix-signature.
        secret: Webhook signing secret (starts with 'whsec_').
        tolerance: Maximum allowed clock skew in seconds (default: 300s / 5 min).

    Returns:
        True if the signature is valid and within tolerance.

    Raises:
        WebhookSecretNotConfiguredError: If secret is missing or empty.
        WebhookMissingHeadersError: If required Svix headers are missing.
        WebhookExpiredError: If timestamp is expired or outside the tolerance window.
        WebhookInvalidSignatureError: If computed signature does not match any header signature.
        WebhookVerificationError: If headers or secret are malformed.
    """
    if not secret or not secret.strip():
        raise WebhookSecretNotConfiguredError("RESEND_WEBHOOK_SECRET is not configured.")

    # Extract Svix headers (case-insensitive fallback)
    header_map = {k.lower().replace("_", "-"): str(v).strip() for k, v in headers.items() if v}
    svix_id = (
        header_map.get("svix-id")
        or header_map.get("http-svix-id")
        or header_map.get("webhook-id")
    )
    svix_timestamp = (
        header_map.get("svix-timestamp")
        or header_map.get("http-svix-timestamp")
        or header_map.get("webhook-timestamp")
    )
    svix_signature = (
        header_map.get("svix-signature")
        or header_map.get("http-svix-signature")
        or header_map.get("webhook-signature")
    )

    if not svix_id or not svix_timestamp or not svix_signature:
        raise WebhookMissingHeadersError("Missing required Svix headers (svix-id, svix-timestamp, svix-signature).")

    # Validate timestamp and prevent replay attacks
    try:
        ts = int(svix_timestamp)
    except (ValueError, TypeError) as exc:
        raise WebhookVerificationError(f"Malformed svix-timestamp header: {exc}") from exc

    current_time = int(time.time())
    if abs(current_time - ts) > tolerance:
        raise WebhookExpiredError(
            f"Webhook timestamp expired or outside tolerance window ({abs(current_time - ts)}s > {tolerance}s)."
        )

    # Decode secret key (strip 'whsec_' prefix if present)
    secret_clean = secret.strip()
    if secret_clean.startswith("whsec_"):
        secret_part = secret_clean[len("whsec_"):]
    else:
        secret_part = secret_clean

    try:
        secret_bytes = base64.b64decode(secret_part)
    except Exception as exc:
        raise WebhookVerificationError(f"Invalid base64 encoding in webhook signing secret: {exc}") from exc

    # Construct signed content: f"{svix_id}.{svix_timestamp}." + raw_body
    if not isinstance(raw_body, (bytes, bytearray)):
        raw_body = str(raw_body).encode("utf-8")

    signed_payload = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + raw_body
    computed_digest = hmac.new(secret_bytes, signed_payload, hashlib.sha256).digest()
    computed_signature = base64.b64encode(computed_digest).decode("utf-8")

    # The svix-signature header may contain multiple space-separated signatures: "v1,sig1 v1,sig2"
    passed_signatures = svix_signature.split(" ")
    matched = False
    for candidate in passed_signatures:
        candidate = candidate.strip()
        if candidate.startswith("v1,"):
            sig_val = candidate[3:]
            if hmac.compare_digest(computed_signature, sig_val):
                matched = True
                break

    if not matched:
        raise WebhookInvalidSignatureError("Computed HMAC-SHA256 signature does not match any provided signature.")

    return True


# ---------------------------------------------------------------------------
# Event Processing & State Transitions
# ---------------------------------------------------------------------------

def handle_resend_webhook_event(
    event: Dict[str, Any],
    svix_id: str,
    svix_timestamp: Optional[int] = None,
    retry_window_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates, deduplicates, and transitions NotificationOutbox state based on
    a verified Resend webhook event.

    Guarantees:
    - Never calls the email client or dispatches emails.
    - Durable event deduplication using outbox.payload JSONField.
    - Correlation via trusted provider_message_id (Resend email_id).
    - Fast-delivery race handling: fresh unmatched events raise WebhookUnmatchedMessageRetryableError
      so the provider can retry while worker completes its database commit.
    - Stale unmatched events (age > retry_window) are acknowledged safely without altering records.
    - Robust bounce data extraction: gracefully handles dicts, strings, lists, null, and missing fields.
    - Terminal-state protection: CANCELLED and PERMANENTLY_FAILED records are never reactivated.
    - Valid delivery evidence is never overwritten by stale/out-of-order events.
    - Row-level locking via select_for_update() prevents concurrent update race conditions.
    """
    if not isinstance(event, dict):
        raise WebhookPayloadError("Event payload must be a JSON object.")

    event_type = event.get("type")
    if not event_type or not isinstance(event_type, str):
        raise WebhookPayloadError("Missing or invalid event 'type'.")

    if event_type not in SUPPORTED_EVENT_TYPES:
        raise WebhookUnsupportedEventError(f"Unsupported event type: '{event_type}'.")

    event_data = event.get("data")
    if not isinstance(event_data, dict):
        raise WebhookPayloadError("Missing or invalid event 'data' object.")

    email_id = event_data.get("email_id")
    if not email_id or not isinstance(email_id, str):
        raise WebhookPayloadError("Missing or invalid 'email_id' in event data.")

    event_created_at = event.get("created_at")
    now = timezone.now()

    with transaction.atomic():
        # Atomically lock and retrieve the outbox record
        outbox = (
            NotificationOutbox.objects.select_for_update()
            .filter(provider_message_id=email_id)
            .first()
        )

        if not outbox:
            # ---------------------------------------------------------------
            # Fast-Delivery Correlation Race vs Stale Unmatched Evaluation
            # ---------------------------------------------------------------
            now_epoch = int(time.time())
            event_ts = svix_timestamp if svix_timestamp is not None else now_epoch
            age_seconds = max(0, now_epoch - event_ts)
            window = retry_window_seconds if retry_window_seconds is not None else getattr(
                settings, "RESEND_WEBHOOK_UNMATCHED_RETRY_WINDOW_SECONDS", 60
            )

            if age_seconds <= window:
                # Fresh event: could be racing the dispatch worker's database commit.
                # Signal a retryable status so Resend retries delivery in a few seconds.
                logger.info(
                    "Unmatched fresh provider_message_id: %s (age %ds <= %ds); signaling retryable conflict.",
                    email_id,
                    age_seconds,
                    window,
                )
                raise WebhookUnmatchedMessageRetryableError(
                    message=f"Provider message ID '{email_id}' not yet committed in database (racing worker); retry requested.",
                    email_id=email_id,
                    age_seconds=age_seconds,
                )
            else:
                # Stale unmatched event beyond the correlation retry window.
                # Acknowledge safely without retry; do NOT alter any unrelated records.
                logger.info(
                    "Unmatched stale provider_message_id: %s (age %ds > %ds); acknowledging safely without retry.",
                    email_id,
                    age_seconds,
                    window,
                )
                return {
                    "status": "ignored",
                    "reason": "unmatched_after_retry_window",
                    "provider_message_id": email_id,
                    "age_seconds": age_seconds,
                }

        # -------------------------------------------------------------------
        # Event Deduplication
        # -------------------------------------------------------------------
        webhook_events = outbox.payload.setdefault("webhook_events", {})
        if svix_id in webhook_events:
            logger.info(
                "Duplicate webhook event %s for record %s (provider_message_id: %s) ignored.",
                svix_id,
                outbox.id,
                email_id,
            )
            return {
                "status": "duplicate",
                "record_id": str(outbox.id),
                "event_id": svix_id,
                "provider_message_id": email_id,
            }

        # Record the incoming event ID durably in the record payload
        webhook_events[svix_id] = {
            "type": event_type,
            "received_at": now.isoformat(),
            "event_created_at": event_created_at,
        }
        outbox.payload["webhook_events"] = webhook_events

        # -------------------------------------------------------------------
        # Terminal-State Protection
        # -------------------------------------------------------------------
        # Cancelled or manually resolved records must NEVER be reactivated.
        if outbox.status in (DeliveryStatus.CANCELLED, DeliveryStatus.PERMANENTLY_FAILED):
            logger.info(
                "Outbox record %s is in terminal state '%s'. Event %s recorded; status unchanged.",
                outbox.id,
                outbox.status,
                event_type,
            )
            outbox.save(update_fields=["payload", "updated_at"])
            return {
                "status": "terminal_state_protected",
                "record_id": str(outbox.id),
                "current_status": outbox.status,
            }

        # -------------------------------------------------------------------
        # State Transitions by Event Type
        # -------------------------------------------------------------------
        if event_type == EVENT_EMAIL_DELIVERED:
            if outbox.status == DeliveryStatus.CONFIRMED_DELIVERED:
                # Already confirmed delivered; idempotent acknowledgement
                outbox.save(update_fields=["payload", "updated_at"])
                return {
                    "status": "already_delivered",
                    "record_id": str(outbox.id),
                }

            # Transition ACCEPTED_BY_PROVIDER (or PROCESSING) to CONFIRMED_DELIVERED
            outbox.status = DeliveryStatus.CONFIRMED_DELIVERED
            parsed_dt = parse_datetime(event_created_at) if event_created_at else None
            outbox.delivered_at = parsed_dt or now
            outbox.last_error = None
            # Release any lingering worker lease
            outbox.locked_at = None
            outbox.locked_by = None
            outbox.lease_token = None
            outbox.save(update_fields=[
                "status",
                "delivered_at",
                "last_error",
                "locked_at",
                "locked_by",
                "lease_token",
                "payload",
                "updated_at",
            ])
            logger.info("Outbox record %s confirmed delivered via webhook.", outbox.id)
            return {
                "status": "confirmed_delivered",
                "record_id": str(outbox.id),
            }

        elif event_type == EVENT_EMAIL_BOUNCED:
            # Safely extract and sanitize bounce data across diverse structures
            raw_bounce = event_data.get("bounce")
            if isinstance(raw_bounce, dict):
                bounce_info = raw_bounce
                raw_type = bounce_info.get("type")
                bounce_type = str(raw_type).strip() if raw_type is not None else "Permanent"
                raw_msg = bounce_info.get("message")
                bounce_msg = str(raw_msg).strip() if raw_msg is not None else "Email rejected by recipient mail server"
            elif raw_bounce is not None:
                bounce_info = {"raw": str(raw_bounce)[:500]}
                bounce_type = "Permanent"
                bounce_msg = str(raw_bounce)[:200]
            else:
                bounce_info = {}
                bounce_type = "Permanent"
                bounce_msg = "Email rejected by recipient mail server"

            sanitized_bounce_msg = sanitize_error_message(bounce_msg)
            bounce_last_error = f"Resend bounce ({bounce_type}): {sanitized_bounce_msg}"[:500]

            # Bounce events must NOT mark a notification as delivered.
            if outbox.status == DeliveryStatus.CONFIRMED_DELIVERED:
                # Do not overwrite valid delivery evidence with stale events
                logger.warning(
                    "Stale bounce received for CONFIRMED_DELIVERED record %s. Preserving delivery status.",
                    outbox.id,
                )
                outbox.payload["stale_bounce"] = bounce_info
                outbox.save(update_fields=["payload", "updated_at"])
                return {
                    "status": "stale_bounce_ignored",
                    "record_id": str(outbox.id),
                }

            outbox.status = DeliveryStatus.PERMANENTLY_FAILED
            outbox.last_error = bounce_last_error
            outbox.payload["bounce"] = bounce_info
            outbox.locked_at = None
            outbox.locked_by = None
            outbox.lease_token = None
            outbox.save(update_fields=[
                "status",
                "last_error",
                "payload",
                "locked_at",
                "locked_by",
                "lease_token",
                "updated_at",
            ])
            logger.warning("Outbox record %s marked PERMANENTLY_FAILED due to bounce.", outbox.id)
            return {
                "status": "marked_permanently_failed",
                "record_id": str(outbox.id),
            }

        elif event_type == EVENT_EMAIL_COMPLAINED:
            # Complaint events must NOT mark a notification as delivered or revert delivery evidence.
            outbox.payload["complaint"] = {
                "received_at": now.isoformat(),
                "data": event_data,
            }
            outbox.save(update_fields=["payload", "updated_at"])
            logger.warning("Outbox record %s received spam complaint.", outbox.id)
            return {
                "status": "complaint_recorded",
                "record_id": str(outbox.id),
            }

        elif event_type == EVENT_EMAIL_SENT:
            # Never treat provider acceptance alone as confirmed delivery.
            # Record sent metadata without modifying status.
            outbox.payload["sent_event"] = {
                "received_at": now.isoformat(),
            }
            outbox.save(update_fields=["payload", "updated_at"])
            return {
                "status": "sent_acknowledged",
                "record_id": str(outbox.id),
            }

        elif event_type == EVENT_EMAIL_DELIVERY_DELAYED:
            outbox.payload["delivery_delayed"] = event_data
            outbox.save(update_fields=["payload", "updated_at"])
            return {
                "status": "delay_recorded",
                "record_id": str(outbox.id),
            }

        # Catch-all for any other supported event
        outbox.save(update_fields=["payload", "updated_at"])
        return {
            "status": "processed",
            "record_id": str(outbox.id),
        }
