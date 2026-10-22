import uuid
from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    HIGH_MATCH_ALERT = "high_match_alert", "High Match Recruiter Alert"
    CANDIDATE_INTERESTED = "candidate_interested", "Candidate Interest Alert"
    MUTUAL_FIT_HANDOFF = "mutual_fit_handoff", "Mutual Fit Handoff Alert"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    ACCEPTED_BY_PROVIDER = "accepted_by_provider", "Accepted by Provider"
    CONFIRMED_DELIVERED = "confirmed_delivered", "Confirmed Delivered"
    PERMANENTLY_FAILED = "permanently_failed", "Permanently Failed"
    CANCELLED = "cancelled", "Cancelled"


class NotificationOutbox(models.Model):
    """
    Durable Transactional Notification Outbox model.
    Guarantees reliable, crash-safe, and privacy-preserving notification dispatch.
    Separates internal match triage eligibility from external email delivery state.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(
        "matching.Match",
        on_delete=models.CASCADE,
        related_name="outbox_notifications",
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.HIGH_MATCH_ALERT,
    )
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        help_text="Deterministic deduplication token (e.g. match:{id}:{type}).",
    )
    status = models.CharField(
        max_length=30,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
    )
    recipient_email = models.EmailField(
        help_text="Destination address (e.g. PEOPLE_PRIME_HANDOFF_EMAIL for recruiter alerts).",
    )
    subject = models.CharField(max_length=255)
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sanitized notification metadata. Strictly no raw resume text, embeddings, or credentials.",
    )
    provider_message_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
        help_text="External message ID returned by Resend (e.g. 're_xxxx') upon acceptance.",
    )
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=5)
    next_attempt_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Scheduled timestamp for the next dispatch attempt (supports exponential backoff).",
    )
    locked_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Timestamp when a worker claimed exclusive processing lease.",
    )
    locked_by = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Identifier of the worker or Celery task holding the active lease.",
    )
    lease_token = models.UUIDField(
        blank=True,
        null=True,
        help_text="Fencing token to safely detect and reject updates from zombie/expired workers.",
    )
    first_attempted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text=(
            "Timestamp when the first dispatch attempt was initiated locally. "
            "Used for provider idempotency window tracking. Note: this timestamp records "
            "the initiation of the first dispatch attempt and does not prove that the provider "
            "received or accepted the request."
        ),
    )
    delivered_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the email provider confirmed message acceptance.",
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Sanitized snippet of the most recent error message (tokens and credentials stripped).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_outbox"
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "notification_type"],
                name="unique_match_notification_outbox",
            )
        ]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"], name="outbox_status_attempt_idx"),
            models.Index(fields=["match", "notification_type"], name="outbox_match_type_idx"),
        ]

    def __str__(self):
        return f"NotificationOutbox ({self.status}): {self.notification_type} -> {self.recipient_email}"
