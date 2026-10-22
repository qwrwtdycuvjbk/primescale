"""
Notifications Views — Resend Webhook Endpoint.

Provides dedicated, secure HTTP ingestion for Resend email lifecycle events.
"""

import json
import logging
from typing import Any, Dict

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .webhooks import (
    WebhookExpiredError,
    WebhookInvalidSignatureError,
    WebhookMissingHeadersError,
    WebhookPayloadError,
    WebhookSecretNotConfiguredError,
    WebhookUnmatchedMessageRetryableError,
    WebhookUnsupportedEventError,
    WebhookVerificationError,
    handle_resend_webhook_event,
    verify_resend_webhook,
)

logger = logging.getLogger(__name__)

# Explicit upper bound on raw request-body size (64 KB)
MAX_WEBHOOK_BODY_SIZE: int = 65536


@method_decorator(csrf_exempt, name="dispatch")
class ResendWebhookView(APIView):
    """
    Dedicated endpoint for ingesting verified Resend webhook events.

    Security & Hardening:
    - HTTP POST only (other methods rejected with 405).
    - Requires application/json Content-Type (rejected with 415).
    - Enforces strict 65,536-byte raw request body limit (rejected with 413).
    - Verifies Svix HMAC-SHA256 signatures before reading or parsing payload.
    - Rejects missing, malformed, expired, or invalid signatures safely (400).
    - Returns 503 if webhook signing secret is not configured on the server.
    - Handles correlation races for fresh unmatched events (409 Conflict).
    - Does not leak secrets, stack traces, or authorization headers.
    - Never triggers email sending.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # 1. Enforce content-type
        content_type = request.content_type or ""
        if not content_type.startswith("application/json"):
            return Response(
                {"error": "Unsupported media type. Content-Type must be application/json."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        # 2. Early Content-Length check to reject oversized bodies before reading
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > MAX_WEBHOOK_BODY_SIZE:
                    return Response(
                        {"error": f"Payload too large. Request body exceeds maximum allowed size of {MAX_WEBHOOK_BODY_SIZE} bytes."},
                        status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )
            except (ValueError, TypeError):
                pass

        # 3. Read raw unparsed bytes from the underlying WSGI request
        raw_body = request.body
        if len(raw_body) > MAX_WEBHOOK_BODY_SIZE:
            return Response(
                {"error": f"Payload too large. Request body exceeds maximum allowed size of {MAX_WEBHOOK_BODY_SIZE} bytes."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        # 4. Extract Svix headers
        headers: Dict[str, str] = {
            "svix-id": request.headers.get("svix-id") or request.META.get("HTTP_SVIX_ID", ""),
            "svix-timestamp": request.headers.get("svix-timestamp") or request.META.get("HTTP_SVIX_TIMESTAMP", ""),
            "svix-signature": request.headers.get("svix-signature") or request.META.get("HTTP_SVIX_SIGNATURE", ""),
        }
        svix_id = headers["svix-id"]

        try:
            svix_timestamp_int = int(headers["svix-timestamp"])
        except (ValueError, TypeError):
            svix_timestamp_int = None

        # 5. Verify cryptographic signature
        secret = getattr(settings, "RESEND_WEBHOOK_SECRET", "")
        tolerance = getattr(settings, "RESEND_WEBHOOK_TOLERANCE_SECONDS", 300)

        try:
            verify_resend_webhook(raw_body, headers, secret=secret, tolerance=tolerance)
        except WebhookSecretNotConfiguredError:
            logger.error("Resend webhook rejected: RESEND_WEBHOOK_SECRET is not configured.")
            return Response(
                {"error": "Webhook signing secret is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (WebhookMissingHeadersError, WebhookExpiredError, WebhookInvalidSignatureError, WebhookVerificationError) as exc:
            logger.warning("Resend webhook signature verification rejected: %s", type(exc).__name__)
            return Response(
                {"error": "Invalid webhook signature or missing/expired headers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 6. Parse and validate JSON payload
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Resend webhook received with malformed JSON body.")
            return Response(
                {"error": "Malformed JSON payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 7. Process event with deduplication, correlation race handling, and state transitions
        try:
            result = handle_resend_webhook_event(
                payload,
                svix_id=svix_id,
                svix_timestamp=svix_timestamp_int,
            )
            return Response(
                {"status": "success", "result": result},
                status=status.HTTP_200_OK,
            )
        except WebhookUnmatchedMessageRetryableError as exc:
            logger.info("Resend webhook racing worker commit: %s", exc)
            return Response(
                {
                    "error": "Provider message not yet registered; retry requested for in-flight transaction.",
                    "provider_message_id": exc.email_id,
                    "retry_after_seconds": 5,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except (WebhookPayloadError, WebhookUnsupportedEventError) as exc:
            logger.warning("Resend webhook payload validation failed: %s", str(exc))
            return Response(
                {"error": f"Invalid event payload: {str(exc)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Unexpected error processing Resend webhook.")
            return Response(
                {"error": "Internal server error processing webhook event."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
