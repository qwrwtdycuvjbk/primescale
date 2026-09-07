import uuid
from django.db import models
from matching.models import Match


class HandoffRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONTACTED = "contacted", "Contacted"
        INTRO_MADE = "intro_made", "Intro Made"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.OneToOneField(
        Match, on_delete=models.CASCADE, related_name="handoff_request"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField(blank=True, null=True)
    notified_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "handoff_requests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Handoff ({self.status}): {self.match}"
