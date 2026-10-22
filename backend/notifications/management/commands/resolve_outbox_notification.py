"""
Management command to securely inspect and resolve NotificationOutbox records
flagged for manual review (Phase 9.12).

Usage:
    python manage.py resolve_outbox_notification <outbox_uuid> --action inspect
    python manage.py resolve_outbox_notification <outbox_uuid> --action dismiss --operator ops-alice --reason "Verified prior email delivered"
    python manage.py resolve_outbox_notification <outbox_uuid> --action retry --operator ops-alice --reason "Confirmed no prior delivery" --confirm-no-prior-delivery
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from notifications.client import sanitize_error_message
from notifications.models import DeliveryStatus, NotificationOutbox
from notifications.outbox_worker import check_notification_eligibility

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Controlled, auditable inspection and resolution for manual-review "
        "NotificationOutbox records. Supports actions: inspect, dismiss, retry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "outbox_id",
            type=str,
            help="UUID primary key of the NotificationOutbox record to inspect or resolve.",
        )
        parser.add_argument(
            "--action",
            type=str,
            choices=["inspect", "dismiss", "retry"],
            required=True,
            help="Action to perform: 'inspect' (read-only), 'dismiss' (mark CANCELLED), or 'retry' (re-queue as PENDING).",
        )
        parser.add_argument(
            "--operator",
            type=str,
            default="",
            help="Non-empty operator identifier (e.g. username or service ID). Required for 'dismiss' and 'retry'.",
        )
        parser.add_argument(
            "--reason",
            type=str,
            default="",
            help="Non-empty justification for the resolution action. Required for 'dismiss' and 'retry'.",
        )
        parser.add_argument(
            "--confirm-no-prior-delivery",
            action="store_true",
            default=False,
            help=(
                "Explicit operator assertion confirming that no prior notification was delivered "
                "for this match. Note: this is an operator assertion, not cryptographic proof. "
                "Required for action 'retry'."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        raw_outbox_id = options["outbox_id"].strip()
        try:
            outbox_uuid = uuid.UUID(raw_outbox_id)
        except (ValueError, AttributeError):
            raise CommandError(f"Invalid outbox record UUID: '{raw_outbox_id}'.")

        action = options["action"]
        operator = options.get("operator", "").strip()
        reason = options.get("reason", "").strip()
        confirm_no_prior_delivery = options.get("confirm_no_prior_delivery", False)

        if action == "inspect":
            self._handle_inspect(outbox_uuid)
        elif action == "dismiss":
            if not operator:
                raise CommandError("Action 'dismiss' requires a non-empty '--operator' identifier.")
            if not reason:
                raise CommandError("Action 'dismiss' requires a non-empty '--reason'.")
            self._handle_dismiss(outbox_uuid, operator=operator, reason=reason)
        elif action == "retry":
            if not operator:
                raise CommandError("Action 'retry' requires a non-empty '--operator' identifier.")
            if not reason:
                raise CommandError("Action 'retry' requires a non-empty '--reason'.")
            if not confirm_no_prior_delivery:
                raise CommandError(
                    "Action 'retry' requires '--confirm-no-prior-delivery'. "
                    "You must explicitly confirm that no prior email was sent before re-queueing."
                )
            self._handle_retry(outbox_uuid, operator=operator, reason=reason)

    def _handle_inspect(self, outbox_uuid: uuid.UUID) -> None:
        """Read-only inspection of the specified outbox record without modifying it."""
        try:
            record = NotificationOutbox.objects.select_related("match", "match__job").get(id=outbox_uuid)
        except NotificationOutbox.DoesNotExist:
            raise CommandError(f"NotificationOutbox record with ID '{outbox_uuid}' does not exist.")

        payload = record.payload or {}
        manual_review = bool(payload.get("manual_review_required"))
        resolved = bool(payload.get("manual_review_resolved"))
        provider_msg_presence = "Present (redacted ID)" if record.provider_message_id else "None"
        delivered_str = record.delivered_at.isoformat() if record.delivered_at else "None"
        first_attempt_str = record.first_attempted_at.isoformat() if getattr(record, "first_attempted_at", None) else "None"
        sanitized_error = sanitize_error_message(record.last_error or "None")

        self.stdout.write(self.style.SUCCESS(f"\n--- NotificationOutbox Record [{record.id}] ---"))
        self.stdout.write(f"  Notification Type:      {record.notification_type}")
        self.stdout.write(f"  Status:                 {record.status}")
        self.stdout.write(f"  Match ID:               {record.match_id}")
        self.stdout.write(f"  Recipient:              {record.recipient_email}")
        self.stdout.write(f"  Subject:                {record.subject}")
        self.stdout.write(f"  Retry Count / Max:      {record.retry_count} / {record.max_retries}")
        self.stdout.write(f"  First Attempted At:     {first_attempt_str}")
        self.stdout.write(f"  Provider Message ID:    {provider_msg_presence}")
        self.stdout.write(f"  Delivered Timestamp:    {delivered_str}")
        self.stdout.write(f"  Manual Review Required: {manual_review}")
        self.stdout.write(f"  Already Resolved:       {resolved}")
        self.stdout.write(f"  Sanitized Last Error:   {sanitized_error}")

        if resolved:
            self.stdout.write(f"  Resolution Action:      {payload.get('manual_review_resolution', 'unknown')}")
            self.stdout.write(f"  Resolved By:            {payload.get('manual_review_resolved_by') or payload.get('manual_review_authorized_by')}")
            self.stdout.write(f"  Resolved At:            {payload.get('manual_review_resolved_at') or payload.get('manual_review_authorized_at')}")

        self.stdout.write(self.style.SUCCESS("--- End of Record ---\n"))

    def _handle_dismiss(self, outbox_uuid: uuid.UUID, operator: str, reason: str) -> None:
        """
        Safely dismisses a manual-review record by transitioning to CANCELLED.
        Enforces atomic row locking, manual-review eligibility checks, and audit preservation.
        """
        now = timezone.now()
        sanitized_reason = sanitize_error_message(reason)

        with transaction.atomic():
            try:
                record = NotificationOutbox.objects.select_for_update().get(id=outbox_uuid)
            except NotificationOutbox.DoesNotExist:
                raise CommandError(f"NotificationOutbox record with ID '{outbox_uuid}' does not exist.")

            payload = dict(record.payload or {})

            # Validation 1: Must be in PERMANENTLY_FAILED state
            if record.status != DeliveryStatus.PERMANENTLY_FAILED:
                raise CommandError(
                    f"Cannot dismiss record {record.id}: status is '{record.status}'. "
                    f"Only records in '{DeliveryStatus.PERMANENTLY_FAILED}' can be dismissed."
                )

            # Validation 2: Must be an eligible manual-review record
            if not payload.get("manual_review_required"):
                raise CommandError(
                    f"Cannot dismiss record {record.id}: 'manual_review_required' flag is not set. "
                    "Arbitrary permanent failures cannot be dismissed via this workflow."
                )

            # Validation 3: Cannot already be resolved
            if payload.get("manual_review_resolved"):
                raise CommandError(
                    f"Record {record.id} has already been resolved "
                    f"({payload.get('manual_review_resolution', 'resolved')})."
                )

            # Validation 4: Must not have evidence of provider acceptance or delivery
            if record.provider_message_id or record.delivered_at:
                raise CommandError(
                    f"Cannot dismiss record {record.id}: record has provider message ID or delivery timestamp. "
                    "Cannot dismiss an accepted/delivered notification."
                )

            # Update audit metadata in payload
            payload["manual_review_resolved"] = True
            payload["manual_review_resolution"] = "dismissed"
            payload["manual_review_resolved_by"] = operator
            payload["manual_review_resolved_at"] = now.isoformat()
            payload["manual_review_dismiss_reason"] = sanitized_reason

            record.status = DeliveryStatus.CANCELLED
            record.last_error = f"Dismissed by operator '{operator}': {sanitized_reason}"
            record.payload = payload
            record.updated_at = now
            record.save(update_fields=["status", "last_error", "payload", "updated_at"])

            logger.info(
                "Manual review outbox record %s dismissed by operator %s: %s",
                record.id,
                operator,
                sanitized_reason,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully dismissed outbox record {record.id}. "
                    f"Status updated to '{DeliveryStatus.CANCELLED}'. No email dispatched."
                )
            )

    def _handle_retry(self, outbox_uuid: uuid.UUID, operator: str, reason: str) -> None:
        """
        Safely authorizes resubmission for an unverified manual-review record.
        Enforces atomic row locking, manual-review eligibility, business eligibility revalidation,
        and transitions status to PENDING for subsequent worker processing.
        Zero emails or network calls are made directly by this command.
        """
        now = timezone.now()
        sanitized_reason = sanitize_error_message(reason)

        with transaction.atomic():
            try:
                record = NotificationOutbox.objects.select_for_update().get(id=outbox_uuid)
            except NotificationOutbox.DoesNotExist:
                raise CommandError(f"NotificationOutbox record with ID '{outbox_uuid}' does not exist.")

            payload = dict(record.payload or {})

            # Validation 1: Must be in PERMANENTLY_FAILED state
            if record.status != DeliveryStatus.PERMANENTLY_FAILED:
                raise CommandError(
                    f"Cannot retry record {record.id}: status is '{record.status}'. "
                    f"Only records in '{DeliveryStatus.PERMANENTLY_FAILED}' can be authorized for retry."
                )

            # Validation 2: Must be an eligible manual-review record
            if not payload.get("manual_review_required"):
                raise CommandError(
                    f"Cannot retry record {record.id}: 'manual_review_required' flag is not set. "
                    "Arbitrary permanent failures cannot be retried via this workflow."
                )

            # Validation 3: Cannot already be resolved
            if payload.get("manual_review_resolved"):
                raise CommandError(
                    f"Record {record.id} has already been resolved "
                    f"({payload.get('manual_review_resolution', 'resolved')})."
                )

            # Validation 4: Must not have evidence of provider acceptance or delivery
            if record.provider_message_id:
                raise CommandError(
                    f"Cannot retry record {record.id}: record already has provider message ID "
                    f"'{record.provider_message_id}'. Duplicate send prevented."
                )
            if record.delivered_at:
                raise CommandError(
                    f"Cannot retry record {record.id}: record already has delivery timestamp. "
                    "Duplicate send prevented."
                )

            # Validation 5: Business eligibility check (Match active, Job active & not expired, Candidate open)
            is_eligible, ineligibility_reason = check_notification_eligibility(record)
            if not is_eligible:
                raise CommandError(
                    f"Cannot retry record {record.id}: business eligibility check failed: {ineligibility_reason}"
                )

            # Update audit metadata in payload
            payload["manual_review_resolved"] = True
            payload["manual_review_resolution"] = "retry_authorized"
            payload["manual_review_authorized_by"] = operator
            payload["manual_review_authorized_at"] = now.isoformat()
            payload["manual_review_retry_reason"] = sanitized_reason
            payload["operator_confirmed_no_prior_delivery"] = True

            # Reset record to PENDING with fresh retry window
            record.status = DeliveryStatus.PENDING
            record.next_attempt_at = now
            record.retry_count = 0
            record.max_retries = 3
            record.locked_at = None
            record.locked_by = None
            record.lease_token = None
            record.last_error = f"Operator '{operator}' authorized retry: {sanitized_reason}"
            record.payload = payload
            record.updated_at = now
            record.save(
                update_fields=[
                    "status",
                    "next_attempt_at",
                    "retry_count",
                    "max_retries",
                    "locked_at",
                    "locked_by",
                    "lease_token",
                    "last_error",
                    "payload",
                    "updated_at",
                ]
            )

            logger.info(
                "Manual review outbox record %s retry authorized by operator %s: %s",
                record.id,
                operator,
                sanitized_reason,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully authorized retry for outbox record {record.id}. "
                    f"Status transitioned to '{DeliveryStatus.PENDING}'. "
                    "Record will be processed by the notification worker upon its next cycle."
                )
            )
