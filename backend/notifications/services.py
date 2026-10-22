"""
Notification Outbox Services for PeopleRemotely.

Handles transactional creation and validation of NotificationOutbox records.
Enforces strict privacy boundaries:
- Never persists resume texts, normalized texts, embedding vectors, or private credentials.
- Strictly validates payload schema.
- Provides deterministic idempotency keys.
- Handles concurrent worker insertion races safely via savepoints.
"""

from __future__ import annotations

import logging
from typing import Any, Final, Optional

from django.conf import settings
from django.db import IntegrityError, transaction

from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType

logger = logging.getLogger(__name__)

# Recruiter alert threshold for high matches
HIGH_MATCH_ALERT_THRESHOLD: Final[float] = 85.0

# Forbidden keys in outbox payloads to prevent accidental leakage of PII or private vectors
PROHIBITED_PAYLOAD_KEYS: Final[frozenset[str]] = frozenset({
    "resume",
    "resume_text",
    "extracted_text",
    "normalized_text",
    "embedding",
    "vector",
    "phone",
    "phone_number",
    "api_key",
    "secret",
    "password",
    "token",
})


def validate_outbox_payload(payload: Any) -> None:
    """
    Recursively validates that the notification payload strictly complies with
    privacy and security constraints:
    - Must be a dictionary.
    - Cannot contain prohibited sensitive keys (resume text, vectors, credentials, phone numbers).
    - Cannot contain raw embedding vector arrays (float lists of length >= 10).
    - Cannot contain excessively long text blobs (> 500 characters).
    """
    if not isinstance(payload, dict):
        raise ValueError(f"Payload must be a dictionary, received {type(payload).__name__}.")

    def _inspect_node(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                lower_key = str(key).strip().lower()
                # Check for prohibited key names
                if lower_key in PROHIBITED_PAYLOAD_KEYS or any(pk in lower_key for pk in ["embedding", "vector", "password", "secret", "api_key"]):
                    raise ValueError(f"Prohibited sensitive key '{key}' found at path '{path}'.")
                if "phone" in lower_key:
                    raise ValueError(f"Prohibited personal contact key '{key}' found at path '{path}'.")
                if "resume" in lower_key and lower_key != "resume_url":
                    raise ValueError(f"Prohibited resume content key '{key}' found at path '{path}'.")
                _inspect_node(val, f"{path}.{key}" if path else str(key))
        elif isinstance(node, (list, tuple)):
            # Check for embedding vector arrays
            if len(node) >= 10 and all(isinstance(x, (int, float)) for x in node[:10]):
                raise ValueError(f"Prohibited vector array detected at path '{path}'.")
            for idx, item in enumerate(node):
                _inspect_node(item, f"{path}[{idx}]")
        elif isinstance(node, str):
            # Check for large raw text dumps
            if len(node) > 500:
                raise ValueError(f"Prohibited long text blob ({len(node)} chars) detected at path '{path}'.")

    _inspect_node(payload)


def create_high_match_outbox_record(
    match: Any,
    job: Any,
    breakdown: Any,
) -> Optional[NotificationOutbox]:
    """
    Transactionally creates a HIGH_MATCH_ALERT NotificationOutbox record within the
    caller's existing database transaction.

    Rules:
    - Strictly requires unrounded final_score >= 85.0.
    - Generates a deterministic idempotency key: match:{match.id}:high_match_alert.
    - Stores only the minimum approved payload: match_id, job_id, job_title, company_name,
      final_score, and permitted score breakdown.
    - Idempotent: if an outbox record already exists for (match, HIGH_MATCH_ALERT),
      returns the existing record without creating a duplicate.
    - Concurrency-safe: uses an inner atomic savepoint so that an IntegrityError from
      a concurrent insert does not corrupt the outer transaction.
    """
    if not match or not job or not breakdown:
        return None

    raw_score = float(getattr(breakdown, "final_score", 0.0))
    if raw_score < HIGH_MATCH_ALERT_THRESHOLD:
        return None

    int_score = int(round(raw_score))
    company_name = job.company.name if (job.company and job.company.name) else ""
    job_title = job.title or "Role"

    recipient_email = getattr(settings, "PEOPLE_PRIME_HANDOFF_EMAIL", "remote@people-prime.com")
    subject = f"[High Match Alert] {int_score}% Match: {job_title} at {company_name or 'Company'}"
    idempotency_key = f"match:{match.id}:{NotificationType.HIGH_MATCH_ALERT}"

    payload = {
        "match_id": str(match.id),
        "job_id": str(job.id),
        "job_title": job_title,
        "company_name": company_name,
        "final_score": int_score,
        "raw_final_score": round(raw_score, 2),
        "score_breakdown": {
            "semantic_score": round(float(getattr(breakdown, "semantic_score", 0.0)), 2),
            "skill_score": round(float(getattr(breakdown, "skill_score", 0.0)), 2),
            "experience_score": round(float(getattr(breakdown, "exp_score", 0.0)), 2),
        },
    }

    validate_outbox_payload(payload)

    with transaction.atomic():
        # 1. Check if already exists under current lock/transaction
        existing_outbox = (
            NotificationOutbox.objects.select_for_update()
            .filter(match=match, notification_type=NotificationType.HIGH_MATCH_ALERT)
            .first()
        )
        if existing_outbox:
            return existing_outbox

        # 2. Insert inside an inner savepoint to guard outer transaction against concurrent race
        try:
            with transaction.atomic():
                return NotificationOutbox.objects.create(
                    match=match,
                    notification_type=NotificationType.HIGH_MATCH_ALERT,
                    idempotency_key=idempotency_key,
                    status=DeliveryStatus.PENDING,
                    recipient_email=recipient_email,
                    subject=subject,
                    payload=payload,
                )
        except IntegrityError:
            # A concurrent worker created the record concurrently; retrieve the winner safely
            return (
                NotificationOutbox.objects.select_for_update()
                .get(match=match, notification_type=NotificationType.HIGH_MATCH_ALERT)
            )
