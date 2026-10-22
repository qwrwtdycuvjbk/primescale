"""
Asynchronous Celery Tasks for Notification Outbox Dispatch and Recovery.

Tasks:
- dispatch_outbox_notifications_task: Claims and dispatches due PENDING outbox records.
- recover_stale_outbox_leases_task: Recovers expired PROCESSING leases and reschedules them.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.conf import settings

from notifications.outbox_worker import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_LEASE_TIMEOUT_SECONDS,
    dispatch_pending_outbox_records,
    recover_stale_outbox_leases,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="notifications.tasks.dispatch_outbox_notifications_task",
    max_retries=1,
)
def dispatch_outbox_notifications_task(self, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    """
    Celery task to claim and dispatch due PENDING outbox notifications via ResendHTTPClient.
    Safe to invoke frequently or repeatedly; skip_locked prevents concurrency collisions.
    Protected by NOTIFICATIONS_DISPATCH_ENABLED kill switch (defaults to False).
    """
    if not getattr(settings, "NOTIFICATIONS_DISPATCH_ENABLED", False):
        logger.info(
            "Notification outbox dispatch is disabled (NOTIFICATIONS_DISPATCH_ENABLED is False). Skipping dispatch."
        )
        return {
            "status": "disabled",
            "claimed_count": 0,
            "results": [],
            "reason": "NOTIFICATIONS_DISPATCH_ENABLED is False",
        }

    worker_id = f"celery-{self.request.id or 'manual'}"
    try:
        summary = dispatch_pending_outbox_records(batch_size=batch_size, worker_id=worker_id)
        logger.info(
            "Outbox dispatch task completed: %d records claimed.",
            summary.get("claimed_count", 0),
        )
        return summary
    except Exception as exc:
        logger.error("Error in dispatch_outbox_notifications_task: %s", exc)
        raise exc


@shared_task(
    bind=True,
    name="notifications.tasks.recover_stale_outbox_leases_task",
    max_retries=1,
)
def recover_stale_outbox_leases_task(
    self,
    lease_timeout: int = DEFAULT_LEASE_TIMEOUT_SECONDS,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """
    Celery task to recover expired PROCESSING outbox leases whose workers crashed or hung.
    Idempotent and safe to run on a regular interval.
    """
    try:
        recovered = recover_stale_outbox_leases(lease_timeout=lease_timeout, batch_size=batch_size)
        logger.info("Outbox lease recovery completed: %d stale leases recovered.", recovered)
        return {"recovered_count": recovered}
    except Exception as exc:
        logger.error("Error in recover_stale_outbox_leases_task: %s", exc)
        raise exc
