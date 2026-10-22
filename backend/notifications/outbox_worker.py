"""
Notification Outbox Dispatch and Recovery Workers for PeopleRemotely.

Features:
- Atomic claiming of PENDING outbox records using select_for_update(skip_locked=True).
- Releases database row locks before performing external HTTP network I/O.
- Fencing tokens (UUID lease_token) protect database updates against zombie or stale workers.
- Pre-dispatch eligibility revalidation (job active/unexpired, candidate opted-in/complete, match not rejected).
- Safe Resend HTTP client dispatch with deterministic idempotency key propagation.
- Provider acceptance (ACCEPTED_BY_PROVIDER) recorded separately from confirmed delivery.
- Bounded exponential backoff with jitter for retryable errors (429, 5xx, timeouts, connection errors).
- Immediate terminal failure (PERMANENTLY_FAILED) for permanent client errors (400, 401, 403, 422) and configuration errors.
- Documented 24-hour provider idempotency cache expiration policy.
- Idempotent lease recovery service for expired PROCESSING claims.
- Never prints or logs secrets, API keys, resume text, embeddings, or private candidate data.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import timedelta
from typing import Any, Final, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from jobs.models import Job
from matching.models import Match
from notifications.client import (
    ResendClientError,
    ResendConfigurationError,
    ResendHTTPClient,
    ResendPermanentError,
    ResendResponse,
    ResendResponseError,
    ResendRetryableError,
    sanitize_error_message,
)
from notifications.models import DeliveryStatus, NotificationOutbox

logger = logging.getLogger(__name__)

# Defaults and Constants
DEFAULT_BATCH_SIZE: Final[int] = 5
DEFAULT_LEASE_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes
BASE_BACKOFF_SECONDS: Final[float] = 10.0
MAX_BACKOFF_SECONDS: Final[float] = 3600.0  # 1 hour
IDEMPOTENCY_WINDOW_SECONDS: Final[int] = 86400  # 24 hours (Resend documented retention window)


def is_ambiguous_outcome(exc: Exception) -> bool:
    """
    Returns True if an exception represents an ambiguous outcome where the provider
    may have received and processed the outbound email before or during the failure:
    - Socket or HTTP read timeouts (request reached provider, response not received).
    - ResendResponseError (provider accepted with HTTP 200/201, but response body was unparseable).
    - HTTP 502/504 gateway timeouts (upstream proxy timed out while provider may have processed).
    """
    if isinstance(exc, ResendResponseError):
        return True
    exc_str = str(exc).lower()
    if "read timeout" in exc_str or "timed out" in exc_str or "timeout" in exc_str:
        return True
    if "502" in exc_str or "504" in exc_str:
        return True
    return False


def check_notification_eligibility(record: NotificationOutbox) -> tuple[bool, str | None]:
    """
    Revalidates business eligibility immediately prior to dispatching:
    - Match exists and is not rejected.
    - Associated job remains active and unexpired.
    - Candidate remains open to matching and has complete profile.

    If any check fails, returns (False, sanitized_reason).
    Does NOT modify match status, employer visibility, or candidate preferences.
    """
    match = (
        Match.objects.select_related("job", "job__company", "candidate_profile")
        .filter(id=record.match_id)
        .first()
    )
    if not match:
        return False, "Match record no longer exists."

    if match.status == Match.Status.REJECTED:
        return False, "Match has been rejected."

    job = match.job
    if not job:
        return False, "Associated job no longer exists."

    if job.status != Job.Status.ACTIVE:
        return False, f"Associated job {job.id} is no longer active (status='{job.status}')."

    if job.expires_at and job.expires_at <= timezone.now():
        return False, f"Associated job {job.id} has expired."

    candidate = match.candidate_profile
    if not candidate:
        return False, "Candidate profile no longer exists."

    if not candidate.open_to_matching:
        return False, f"Candidate {candidate.id} has opted out of matching."

    if not candidate.profile_complete:
        return False, f"Candidate {candidate.id} profile is incomplete."

    return True, None


def claim_pending_records(
    batch_size: int = DEFAULT_BATCH_SIZE,
    worker_id: str | None = None,
) -> list[tuple[NotificationOutbox, uuid.UUID]]:
    """
    Atomically claims up to `batch_size` PENDING outbox records whose next_attempt_at is due.

    Key Concurrency Semantics:
    - Uses PostgreSQL transactions with `select_for_update(skip_locked=True)`.
    - Multiple parallel workers skip locked records and claim disjoint batches without contention.
    - Assigns unique lease_token (UUID), locked_at, and locked_by identifier.
    - Commits transaction immediately upon claiming: ROW LOCKS ARE RELEASED BEFORE NETWORK I/O.
    """
    worker_tag = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    now = timezone.now()
    claimed: list[tuple[NotificationOutbox, uuid.UUID]] = []

    with transaction.atomic():
        records = list(
            NotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                status=DeliveryStatus.PENDING,
                next_attempt_at__lte=now,
            )
            .order_by("next_attempt_at", "created_at")[:batch_size]
        )

        for record in records:
            lease_token = uuid.uuid4()
            record.status = DeliveryStatus.PROCESSING
            record.locked_at = now
            record.locked_by = worker_tag
            record.lease_token = lease_token
            record.save(
                update_fields=["status", "locked_at", "locked_by", "lease_token", "updated_at"]
            )
            claimed.append((record, lease_token))

    return claimed


def build_email_content_from_payload(payload: dict[str, Any]) -> tuple[str, str]:
    """
    Formats the HTML and plaintext outbound email body exclusively from approved
    sanitized outbox payload fields. Strictly no resume text, embeddings, or passwords.
    """
    job_title = payload.get("job_title", "Role")
    company_name = payload.get("company_name", "Company")
    final_score = payload.get("final_score", 0)
    match_id = payload.get("match_id", "")

    html_content = (
        f"<p>A candidate match has met the high-confidence triage threshold (&ge; 85%).</p>"
        f"<ul>"
        f"<li><strong>Role:</strong> {job_title}</li>"
        f"<li><strong>Company:</strong> {company_name}</li>"
        f"<li><strong>Match Score:</strong> {final_score}%</li>"
        f"<li><strong>Match ID:</strong> {match_id}</li>"
        f"</ul>"
        f"<p>Log in to the Recruiter / Admin dashboard to review and approve this match.</p>"
        f"<p>&mdash; People Remotely Ops Notification System</p>"
    )

    text_content = (
        f"A candidate match has met the high-confidence triage threshold (>= 85%).\n\n"
        f"Role: {job_title}\n"
        f"Company: {company_name}\n"
        f"Match Score: {final_score}%\n"
        f"Match ID: {match_id}\n\n"
        f"Log in to the Recruiter / Admin dashboard to review and approve this match.\n\n"
        f"— People Remotely Ops Notification System"
    )

    return html_content, text_content


def dispatch_claimed_record(
    record: NotificationOutbox,
    lease_token: uuid.UUID,
    client: ResendHTTPClient | None = None,
) -> dict[str, Any]:
    """
    Dispatches a single claimed outbox record:
    1. Refreshes the lease immediately before dispatch via conditional update:
       requires (id=record_id, status=PROCESSING, lease_token=lease_token).
       If refresh fails (e.g. lease expired, recovered, or replaced), execution aborts
       immediately without initiating network I/O.
    2. Revalidates eligibility: marks CANCELLED if match/job/candidate no longer qualifies.
    3. Builds email from approved payload fields.
    4. Sends via ResendHTTPClient using the deterministic idempotency_key.
    5. Successful provider acceptance persists provider_message_id and status ACCEPTED_BY_PROVIDER.
       Note: delivered_at remains unset (None) until confirmed by delivery webhook.
    6. Applies bounded retry with backoff for retryable errors within the safe idempotency window.
    7. Transitions ambiguous outcomes (e.g. read timeouts) past the 24h idempotency window
       to PERMANENTLY_FAILED for manual review to prevent duplicate delivery.
    """
    record_id = record.id
    now = timezone.now()

    # 1. Pre-dispatch lease refresh (fencing check)
    refreshed_rows = NotificationOutbox.objects.filter(
        id=record_id,
        status=DeliveryStatus.PROCESSING,
        lease_token=lease_token,
    ).update(
        locked_at=now,
        updated_at=now,
    )
    if refreshed_rows == 0:
        logger.warning(
            "Fencing rejection: lease expired or replaced before dispatch for record %s (lease_token=%s). Aborting dispatch.",
            record_id,
            lease_token,
        )
        return {"status": "fencing_rejected", "record_id": str(record_id)}

    # 2. Eligibility Check
    is_eligible, ineligibility_reason = check_notification_eligibility(record)
    if not is_eligible:
        sanitized_reason = sanitize_error_message(f"Ineligible: {ineligibility_reason}")
        rows = NotificationOutbox.objects.filter(
            id=record_id,
            lease_token=lease_token,
            status=DeliveryStatus.PROCESSING,
        ).update(
            status=DeliveryStatus.CANCELLED,
            last_error=sanitized_reason,
            locked_at=None,
            locked_by=None,
            lease_token=None,
            updated_at=now,
        )
        if rows == 0:
            logger.warning("Fencing rejected cancellation for %s: lease token mismatch.", record_id)
            return {"status": "fencing_rejected", "record_id": str(record_id)}
        return {"status": "cancelled", "record_id": str(record_id), "reason": ineligibility_reason}

    # 3. Build email content
    html_content, text_content = build_email_content_from_payload(record.payload or {})
    resend_client = client or ResendHTTPClient()

    # 4. Atomically and durably record first_attempted_at before initiating external HTTP request
    # Note: first_attempted_at marks when the local system initiated the first outbound dispatch
    # attempt; it does NOT prove that the external provider received, accepted, or processed the request.
    # It establishes an accurate start boundary for provider idempotency window tracking.
    # Never overwrite an existing first_attempted_at on subsequent retries.
    first_attempt = getattr(record, "first_attempted_at", None)
    if first_attempt is None:
        rows = NotificationOutbox.objects.filter(
            id=record_id,
            status=DeliveryStatus.PROCESSING,
            lease_token=lease_token,
            first_attempted_at__isnull=True,
        ).update(
            first_attempted_at=now,
            updated_at=now,
        )
        if rows > 0:
            record.first_attempted_at = now
        else:
            current_row = (
                NotificationOutbox.objects.filter(id=record_id)
                .values("first_attempted_at", "lease_token", "status")
                .first()
            )
            if (
                not current_row
                or current_row["lease_token"] != lease_token
                or current_row["status"] != DeliveryStatus.PROCESSING
            ):
                logger.warning(
                    "Fencing rejection before HTTP dispatch for record %s (lease_token=%s). Aborting dispatch.",
                    record_id,
                    lease_token,
                )
                return {"status": "fencing_rejected", "record_id": str(record_id)}
            record.first_attempted_at = current_row["first_attempted_at"] or now

    # 5. External HTTP Request with deterministic idempotency_key
    try:
        response: ResendResponse = resend_client.send_email(
            to=record.recipient_email,
            subject=record.subject,
            html=html_content,
            text=text_content,
            idempotency_key=record.idempotency_key,
        )

        # 6. Successful Provider Acceptance
        # Semantics: delivered_at is NOT populated here. Provider acceptance (HTTP 200/201)
        # records ACCEPTED_BY_PROVIDER and provider_message_id. Confirmed delivery requires
        # verified delivery webhooks in a future phase.
        rows = NotificationOutbox.objects.filter(
            id=record_id,
            lease_token=lease_token,
            status=DeliveryStatus.PROCESSING,
        ).update(
            status=DeliveryStatus.ACCEPTED_BY_PROVIDER,
            provider_message_id=response.message_id,
            locked_at=None,
            locked_by=None,
            lease_token=None,
            updated_at=now,
        )

        if rows == 0:
            logger.warning(
                "Fencing rejection: record %s accepted by provider (%s), but lease token expired/replaced.",
                record_id,
                response.message_id,
            )
            return {
                "status": "fencing_rejected",
                "record_id": str(record_id),
                "provider_message_id": response.message_id,
            }

        return {
            "status": "accepted_by_provider",
            "record_id": str(record_id),
            "provider_message_id": response.message_id,
        }

    except (ResendRetryableError, ResendResponseError) as exc:
        new_retry_count = record.retry_count + 1
        window_start = getattr(record, "first_attempted_at", None) or record.created_at
        age_seconds = (now - window_start).total_seconds()
        is_ambiguous = is_ambiguous_outcome(exc)

        # Retry limit exhaustion -> terminal failure
        if new_retry_count >= record.max_retries:
            err_msg = sanitize_error_message(f"Max retries ({record.max_retries}) exhausted: {str(exc)}")
            rows = NotificationOutbox.objects.filter(
                id=record_id,
                lease_token=lease_token,
                status=DeliveryStatus.PROCESSING,
            ).update(
                status=DeliveryStatus.PERMANENTLY_FAILED,
                retry_count=new_retry_count,
                last_error=err_msg,
                locked_at=None,
                locked_by=None,
                lease_token=None,
                updated_at=now,
            )
            return {"status": "permanently_failed", "record_id": str(record_id), "error": err_msg}

        # Provider Idempotency Window Expiry Protection:
        # Resend's documented idempotency window is 24 hours (86,400s) beginning from the first
        # HTTP request received by Resend with that Idempotency-Key.
        # We track the time elapsed since the first actual dispatch attempt (`first_attempted_at`).
        # Note: A local `first_attempted_at` timestamp records when the local client initiated dispatch;
        # it does not prove the provider actually received the request (e.g. if a network partition occurred
        # before TCP handshake). However, it establishes a strictly more accurate starting boundary than `created_at`
        # for provider idempotency window expiry, preventing false-positive manual review triggers for records
        # that sat queued in the database prior to their first dispatch attempt.
        # For legacy records lacking `first_attempted_at`, we safely fall back to `created_at`.
        if is_ambiguous and age_seconds >= IDEMPOTENCY_WINDOW_SECONDS:
            err_msg = sanitize_error_message(
                f"Automated retry halted: ambiguous provider outcome ({str(exc)}) and elapsed time ({int(age_seconds)}s) "
                f"exceeds provider 24-hour idempotency window; manual review required to prevent duplicate delivery."
            )
            payload = dict(record.payload or {})
            payload["manual_review_required"] = True
            rows = NotificationOutbox.objects.filter(
                id=record_id,
                lease_token=lease_token,
                status=DeliveryStatus.PROCESSING,
            ).update(
                status=DeliveryStatus.PERMANENTLY_FAILED,
                retry_count=new_retry_count,
                last_error=err_msg,
                payload=payload,
                locked_at=None,
                locked_by=None,
                lease_token=None,
                updated_at=now,
            )
            return {"status": "permanently_failed", "record_id": str(record_id), "error": err_msg}

        # Safely retryable within valid idempotency window: bounded exponential backoff with jitter
        backoff = min(BASE_BACKOFF_SECONDS * (2 ** record.retry_count) + random.uniform(0.5, 2.0), MAX_BACKOFF_SECONDS)
        next_attempt = now + timedelta(seconds=backoff)
        err_msg = sanitize_error_message(str(exc))

        rows = NotificationOutbox.objects.filter(
            id=record_id,
            lease_token=lease_token,
            status=DeliveryStatus.PROCESSING,
        ).update(
            status=DeliveryStatus.PENDING,
            retry_count=new_retry_count,
            next_attempt_at=next_attempt,
            last_error=err_msg,
            locked_at=None,
            locked_by=None,
            lease_token=None,
            updated_at=now,
        )
        return {
            "status": "rescheduled",
            "record_id": str(record_id),
            "retry_count": new_retry_count,
            "next_attempt_at": next_attempt.isoformat(),
            "error": err_msg,
        }

    except (ResendPermanentError, ResendConfigurationError) as exc:
        # Permanent client error (400, 401, 403, 422, invalid sender/credentials) -> never retry repeatedly
        err_msg = sanitize_error_message(f"Permanent failure: {str(exc)}")
        rows = NotificationOutbox.objects.filter(
            id=record_id,
            lease_token=lease_token,
            status=DeliveryStatus.PROCESSING,
        ).update(
            status=DeliveryStatus.PERMANENTLY_FAILED,
            last_error=err_msg,
            locked_at=None,
            locked_by=None,
            lease_token=None,
            updated_at=now,
        )
        return {"status": "permanently_failed", "record_id": str(record_id), "error": err_msg}

    except Exception as exc:
        # Unexpected exception -> check idempotency window if ambiguous, else retry with backoff
        new_retry_count = record.retry_count + 1
        window_start = getattr(record, "first_attempted_at", None) or record.created_at
        age_seconds = (now - window_start).total_seconds()
        is_ambiguous = is_ambiguous_outcome(exc)
        err_msg = sanitize_error_message(f"Unexpected error: {type(exc).__name__}: {str(exc)}")

        if new_retry_count >= record.max_retries:
            NotificationOutbox.objects.filter(
                id=record_id,
                lease_token=lease_token,
                status=DeliveryStatus.PROCESSING,
            ).update(
                status=DeliveryStatus.PERMANENTLY_FAILED,
                retry_count=new_retry_count,
                last_error=err_msg,
                locked_at=None,
                locked_by=None,
                lease_token=None,
                updated_at=now,
            )
            return {"status": "permanently_failed", "record_id": str(record_id), "error": err_msg}

        if is_ambiguous and age_seconds >= IDEMPOTENCY_WINDOW_SECONDS:
            ambiguous_msg = sanitize_error_message(
                f"Automated retry halted: ambiguous outcome ({err_msg}) and elapsed time ({int(age_seconds)}s) "
                f"exceeds provider 24-hour idempotency window; manual review required to prevent duplicate delivery."
            )
            payload = dict(record.payload or {})
            payload["manual_review_required"] = True
            NotificationOutbox.objects.filter(
                id=record_id,
                lease_token=lease_token,
                status=DeliveryStatus.PROCESSING,
            ).update(
                status=DeliveryStatus.PERMANENTLY_FAILED,
                retry_count=new_retry_count,
                last_error=ambiguous_msg,
                payload=payload,
                locked_at=None,
                locked_by=None,
                lease_token=None,
                updated_at=now,
            )
            return {"status": "permanently_failed", "record_id": str(record_id), "error": ambiguous_msg}

        backoff = min(BASE_BACKOFF_SECONDS * (2 ** record.retry_count) + random.uniform(0.5, 2.0), MAX_BACKOFF_SECONDS)
        next_attempt = now + timedelta(seconds=backoff)
        NotificationOutbox.objects.filter(
            id=record_id,
            lease_token=lease_token,
            status=DeliveryStatus.PROCESSING,
        ).update(
            status=DeliveryStatus.PENDING,
            retry_count=new_retry_count,
            next_attempt_at=next_attempt,
            last_error=err_msg,
            locked_at=None,
            locked_by=None,
            lease_token=None,
            updated_at=now,
        )
        return {
            "status": "rescheduled",
            "record_id": str(record_id),
            "retry_count": new_retry_count,
            "error": err_msg,
        }



def dispatch_pending_outbox_records(
    batch_size: int = DEFAULT_BATCH_SIZE,
    worker_id: str | None = None,
    client: ResendHTTPClient | None = None,
) -> dict[str, Any]:
    """
    Main dispatch entrypoint:
    Claims due PENDING records and dispatches them sequentially.
    Releases database locks between claims and dispatch.
    """
    claimed = claim_pending_records(batch_size=batch_size, worker_id=worker_id)
    results = []

    for record, lease_token in claimed:
        res = dispatch_claimed_record(record, lease_token, client=client)
        results.append(res)

    return {
        "claimed_count": len(claimed),
        "results": results,
    }


def recover_stale_outbox_leases(
    lease_timeout: int = DEFAULT_LEASE_TIMEOUT_SECONDS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """
    Recovery callable for stale PROCESSING records:
    1. Finds records in PROCESSING state where locked_at < now - lease_timeout.
    2. Atomically claims them using select_for_update(skip_locked=True).
    3. Increments retry_count.
    4. If retry_count >= max_retries, transitions to PERMANENTLY_FAILED.
    5. If retries remain, resets status to PENDING with backoff.
    6. Clears locked_at, locked_by, and lease_token.
    Fencing Limitation Documentation:
    Database lease fencing ensures that a stale worker cannot update the outbox record
    after recovery has taken place (its lease_token is now invalid).
    However, database fencing CANNOT stop an external HTTP request already in flight
    from an old worker. Resend's provider-level Idempotency-Key guarantees that even if
    an old in-flight request arrives, the provider deduplicates it without double-sending.
    """
    now = timezone.now()
    cutoff = now - timedelta(seconds=lease_timeout)
    recovered_count = 0

    with transaction.atomic():
        stale_records = list(
            NotificationOutbox.objects.select_for_update(skip_locked=True)
            .filter(
                status=DeliveryStatus.PROCESSING,
                locked_at__lt=cutoff,
            )[:batch_size]
        )

        for record in stale_records:
            new_retry_count = record.retry_count + 1
            if new_retry_count >= record.max_retries:
                record.status = DeliveryStatus.PERMANENTLY_FAILED
                record.last_error = sanitize_error_message(
                    f"Lease expired after {lease_timeout}s (worker={record.locked_by}); max retries ({record.max_retries}) exhausted."
                )
            else:
                record.status = DeliveryStatus.PENDING
                backoff = min(BASE_BACKOFF_SECONDS * (2 ** record.retry_count), MAX_BACKOFF_SECONDS)
                record.next_attempt_at = now + timedelta(seconds=backoff)
                record.last_error = sanitize_error_message(
                    f"Lease expired after {lease_timeout}s (worker={record.locked_by}); recovered for retry."
                )

            record.retry_count = new_retry_count
            record.locked_at = None
            record.locked_by = None
            record.lease_token = None
            record.save(
                update_fields=[
                    "status",
                    "retry_count",
                    "next_attempt_at",
                    "last_error",
                    "locked_at",
                    "locked_by",
                    "lease_token",
                    "updated_at",
                ]
            )
            recovered_count += 1

    return recovered_count
