from typing import Optional
from django.db import transaction
from django.utils import timezone
from matching.models import Match
from .models import HandoffRequest


def create_mutual_fit_handoff(match_id: str) -> Optional[HandoffRequest]:
    """
    Idempotently creates a HandoffRequest when a match reaches mutual_fit status.
    """
    try:
        match = Match.objects.select_related(
            "job", "job__company", "job__posted_by", "candidate_profile", "candidate_profile__user"
        ).get(id=match_id)
    except Match.DoesNotExist:
        return None

    with transaction.atomic():
        handoff, created = HandoffRequest.objects.get_or_create(
            match=match,
            defaults={
                "status": HandoffRequest.Status.PENDING,
                "notified_at": timezone.now(),
            },
        )
    return handoff


def update_handoff_status(
    handoff_id: str, status: Optional[str] = None, notes: Optional[str] = None
) -> Optional[HandoffRequest]:
    """
    Updates the status and internal recruiter notes on a handoff request.
    """
    try:
        handoff = HandoffRequest.objects.get(id=handoff_id)
    except HandoffRequest.DoesNotExist:
        return None

    if status and status in [c[0] for c in HandoffRequest.Status.choices]:
        handoff.status = status
    if notes is not None:
        handoff.notes = notes

    handoff.save()
    return handoff
