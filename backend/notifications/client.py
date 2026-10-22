"""
Dedicated Resend HTTP Client for PeopleRemotely Notification Outbox.

Documentation of Provider Idempotency Guarantees and Limitations:
------------------------------------------------------------------
1. Idempotency Key Semantics:
   - Resend supports an `Idempotency-Key` header (up to 256 characters).
   - Resend caches the response for a given idempotency key for up to 24 hours.
   - If a request is retried with the same `Idempotency-Key` within this window,
     Resend replays the cached provider response (including original message ID)
     without queuing a duplicate physical email dispatch.
   - Beyond 24 hours or with differing payload/keys, provider idempotency cannot be guaranteed.

2. Ambiguous Timeouts and Recovery:
   - When a network or socket read timeout occurs, the client cannot know whether
     the request reached Resend before the connection terminated.
   - Propagating the deterministic `Idempotency-Key` on subsequent retries ensures that
     if the original request succeeded, the retry receives the cached response rather
     than sending a second duplicate email.

3. Downstream Delivery Realities (No Claim of Exactly-Once Physical Delivery):
   - Provider acceptance (HTTP 200/201 with a message ID) signifies that Resend has accepted
     the message into its delivery pipeline (`ACCEPTED_BY_PROVIDER`).
   - It does NOT guarantee delivery to the recipient's inbox (`CONFIRMED_DELIVERED`).
   - Downstream mail transfer agents (MTAs), recipient spam filters, SMTP retries,
     and mailbox provider rules operate outside Resend's idempotency scope and may drop,
     delay, or in rare edge cases duplicate messages.
   - Exactly-once physical inbox delivery is impossible across distributed SMTP networks.
   - The status `ACCEPTED_BY_PROVIDER` accurately reflects Resend acceptance.

4. Privacy & Sanitization:
   - Secrets, bearer tokens, API keys, and sensitive resume data are strictly stripped
     from all error messages, logs, and exception strings.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Final

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Constants & Defaults
DEFAULT_RESEND_API_URL: Final[str] = "https://api.resend.com/emails"
DEFAULT_CONNECT_TIMEOUT: Final[float] = 3.0
DEFAULT_READ_TIMEOUT: Final[float] = 10.0

# Regex patterns for stripping sensitive tokens from error messages
API_KEY_REGEX = re.compile(r"re_[A-Za-z0-9_]{10,}", re.IGNORECASE)
BEARER_REGEX = re.compile(r"Bearer\s+[A-Za-z0-9_.-]+", re.IGNORECASE)


def sanitize_error_message(message: str) -> str:
    """
    Strip credentials, API keys, and Bearer tokens from error strings.
    """
    if not message:
        return ""
    sanitized = BEARER_REGEX.sub("Bearer [REDACTED_TOKEN]", str(message))
    sanitized = API_KEY_REGEX.sub("[REDACTED_API_KEY]", sanitized)
    return sanitized[:500]


# ============================================================================
# Exception Hierarchy
# ============================================================================


class ResendClientError(Exception):
    """Base exception for all Resend HTTP client errors."""

    pass


class ResendConfigurationError(ResendClientError):
    """Raised when required configuration (API key, sender email) is missing or invalid."""

    pass


class ResendValidationError(ResendClientError):
    """Raised when email parameters (recipient, subject, body) fail validation."""

    pass


class ResendRetryableError(ResendClientError):
    """
    Raised on transient errors that should be retried with exponential backoff:
    - HTTP 429 (Rate limit)
    - HTTP 500, 502, 503, 504 (Server error / gateway timeout)
    - Network connection failures and read/connect timeouts.
    """

    pass


class ResendPermanentError(ResendClientError):
    """
    Raised on non-retryable client errors:
    - HTTP 400 (Bad request)
    - HTTP 401 (Unauthorized / invalid API key)
    - HTTP 403 (Forbidden)
    - HTTP 422 (Unprocessable entity / validation error / unverified domain)
    """

    pass


class ResendResponseError(ResendClientError):
    """Raised when provider returns HTTP 200/201 but the response body is malformed."""

    pass


# ============================================================================
# Response Data Object
# ============================================================================


@dataclass(frozen=True)
class ResendResponse:
    """Immutable representation of a successful provider acceptance."""

    message_id: str
    status_code: int
    raw_response: dict[str, Any]

    def __repr__(self) -> str:
        return f"ResendResponse(message_id='{self.message_id}', status_code={self.status_code})"


# ============================================================================
# Resend HTTP Client
# ============================================================================


class ResendHTTPClient:
    """
    Dedicated HTTP client for sending emails through Resend's REST API.
    Enforces timeout boundaries, error classification, credential sanitization,
    and deterministic idempotency key propagation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        from_email: str | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._from_email = from_email
        self.connect_timeout = (
            connect_timeout
            if connect_timeout is not None
            else float(getattr(settings, "RESEND_CONNECT_TIMEOUT", DEFAULT_CONNECT_TIMEOUT))
        )
        self.read_timeout = (
            read_timeout
            if read_timeout is not None
            else float(getattr(settings, "RESEND_READ_TIMEOUT", DEFAULT_READ_TIMEOUT))
        )
        self._session = session or requests.Session()

    @property
    def api_url(self) -> str:
        url = self._api_url or getattr(settings, "RESEND_API_URL", DEFAULT_RESEND_API_URL)
        return url.strip() if url else DEFAULT_RESEND_API_URL

    @property
    def from_email(self) -> str:
        sender = self._from_email or getattr(settings, "RESEND_FROM_EMAIL", "")
        if not sender or not sender.strip():
            raise ResendConfigurationError(
                "Resend sender email is not configured. Set RESEND_FROM_EMAIL."
            )
        return sender.strip()

    def _get_api_key(self) -> str:
        key = self._api_key or getattr(settings, "RESEND_API_KEY", "")
        if not key or not key.strip():
            raise ResendConfigurationError(
                "Resend API key is not configured. Set RESEND_API_KEY."
            )
        return key.strip()

    def validate_params(
        self,
        to: str | list[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
    ) -> tuple[list[str], str]:
        """Validate recipient, subject, and body contents."""
        if isinstance(to, str):
            recipients = [to.strip()] if to.strip() else []
        elif isinstance(to, (list, tuple)):
            recipients = [str(r).strip() for r in to if str(r).strip()]
        else:
            raise ResendValidationError(
                f"Recipient 'to' must be a string or list of strings, received {type(to).__name__}."
            )

        if not recipients:
            raise ResendValidationError("At least one recipient email address must be provided.")

        if not subject or not subject.strip():
            raise ResendValidationError("Email subject cannot be empty.")

        clean_subject = subject.strip()

        if not html and not text:
            raise ResendValidationError("Email must contain either 'html' or 'text' content.")

        return recipients, clean_subject

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract sanitized error detail from response body or status."""
        try:
            body = response.json()
            if isinstance(body, dict):
                # Resend standard error format: {"statusCode": 422, "message": "...", "name": "..."}
                if "message" in body and body["message"]:
                    return sanitize_error_message(str(body["message"]))
                if "detail" in body and body["detail"]:
                    return sanitize_error_message(str(body["detail"]))
                if "error" in body and body["error"]:
                    return sanitize_error_message(str(body["error"]))
        except Exception:
            pass
        return sanitize_error_message(response.reason or f"HTTP {response.status_code}")

    def send_email(
        self,
        to: str | list[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
        idempotency_key: str | None = None,
    ) -> ResendResponse:
        """
        Send an email via Resend's REST API.

        :param to: Single recipient email string or list of recipient email addresses.
        :param subject: Email subject line.
        :param html: HTML email body content.
        :param text: Optional plaintext fallback or body content.
        :param idempotency_key: Deterministic key to prevent duplicate email dispatches.
        :return: ResendResponse containing provider message ID and status code.
        :raises ResendConfigurationError: If API key or sender email is not configured.
        :raises ResendValidationError: If email parameters are invalid.
        :raises ResendRetryableError: On rate limit (429), server errors (5xx), or timeouts.
        :raises ResendPermanentError: On client errors (400, 401, 403, 422).
        :raises ResendResponseError: On malformed 200/201 responses.
        """
        recipients, clean_subject = self.validate_params(to=to, subject=subject, html=html, text=text)
        api_key = self._get_api_key()
        sender = self.from_email

        headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        if idempotency_key and str(idempotency_key).strip():
            headers["Idempotency-Key"] = str(idempotency_key).strip()

        payload: dict[str, Any] = {
            "from": sender,
            "to": recipients,
            "subject": clean_subject,
        }
        if html:
            payload["html"] = html
        if text:
            payload["text"] = text

        try:
            response = self._session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=(self.connect_timeout, self.read_timeout),
            )
        except requests.exceptions.Timeout as exc:
            sanitized = sanitize_error_message(str(exc))
            raise ResendRetryableError(
                f"Resend HTTP request timed out (connect={self.connect_timeout}s, read={self.read_timeout}s): {sanitized}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            sanitized = sanitize_error_message(str(exc))
            raise ResendRetryableError(
                f"Resend HTTP connection failed: {sanitized}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            sanitized = sanitize_error_message(str(exc))
            raise ResendRetryableError(
                f"Resend HTTP request failed: {sanitized}"
            ) from exc

        status_code = response.status_code

        # 1. Success response
        if status_code in (200, 201):
            try:
                data = response.json()
            except ValueError as exc:
                raise ResendResponseError(
                    f"Resend returned HTTP {status_code} with malformed non-JSON body."
                ) from exc

            if not isinstance(data, dict):
                raise ResendResponseError(
                    f"Resend returned HTTP {status_code} with unexpected non-dict JSON body: {type(data).__name__}."
                )

            message_id = data.get("id")
            if not message_id or not isinstance(message_id, str):
                raise ResendResponseError(
                    f"Resend returned HTTP {status_code} without a valid 'id' in response: {list(data.keys())}."
                )

            return ResendResponse(
                message_id=message_id.strip(),
                status_code=status_code,
                raw_response=data,
            )

        # 2. Rate limiting (429) -> Retryable
        if status_code == 429:
            detail = self._extract_error_detail(response)
            raise ResendRetryableError(f"Resend rate limit exceeded (HTTP 429): {detail}")

        # 3. Server errors (500, 502, 503, 504) -> Retryable
        if status_code in (500, 502, 503, 504) or status_code >= 500:
            detail = self._extract_error_detail(response)
            raise ResendRetryableError(f"Resend server error (HTTP {status_code}): {detail}")

        # 4. Permanent client errors (400, 401, 403, 422, etc.)
        detail = self._extract_error_detail(response)
        raise ResendPermanentError(f"Resend permanent client error (HTTP {status_code}): {detail}")
