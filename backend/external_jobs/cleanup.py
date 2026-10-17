import logging
import time
from datetime import timedelta
from typing import Optional, Sequence

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from external_jobs.models import ExternalJob, ExternalJobSource

logger = logging.getLogger(__name__)

DEFAULT_RETENTION_DAYS = 21
DEFAULT_BATCH_SIZE = 1000
ALLOWED_CLEANUP_PROVIDERS = ("adzuna", "himalayas")
PROTECTED_PROVIDERS = ("people_prime",)


def cleanup_external_jobs(
    days: int = DEFAULT_RETENTION_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    execute: bool = False,
    providers: Sequence[str] = ALLOWED_CLEANUP_PROVIDERS,
    sleep_between_batches: float = 0.0,
) -> dict:
    """
    Safely identifies and optionally deletes stale external jobs from third-party aggregators
    where the original publication date (posted_at) is strictly older than `days` days.

    Safety Guards:
    - Target providers: strictly restricted to `providers` (default: 'adzuna', 'himalayas').
    - Protected providers: 'people_prime' ATS jobs and first-party employer jobs are never touched.
    - Missing/invalid dates: listings with posted_at=None are conservative skipped and reported.
      They are NEVER deleted based on fetched_at or created_at.
    - Dry-run default: execute must be explicitly True to perform SQL DELETE.
    - Memory safety: batching operates over primary keys, not full model objects.
    - Counter reconciliation: active_jobs_count is recalculated for affected sources after deletion.
    """
    start_time = timezone.now()
    cutoff_date = start_time - timedelta(days=days)

    # Sanitize target providers to guarantee protected providers are never included
    sanitized_providers = [
        p.lower().strip()
        for p in providers
        if p.lower().strip() not in PROTECTED_PROVIDERS
    ]

    base_qs = ExternalJob.objects.filter(source__provider_code__in=sanitized_providers)
    scanned_count = base_qs.count()

    # Missing/invalid publication dates (conservative: skipped from deletion)
    missing_date_qs = base_qs.filter(posted_at__isnull=True)
    skipped_missing_date_count = missing_date_qs.count()

    # Fresh listings within retention window
    fresh_qs = base_qs.filter(posted_at__gte=cutoff_date)
    skipped_fresh_count = fresh_qs.count()

    # Listings strictly older than the retention cutoff
    eligible_qs = base_qs.filter(posted_at__lt=cutoff_date)
    eligible_count = eligible_qs.count()

    # Breakdown by provider
    eligible_by_provider = {}
    for prov in sanitized_providers:
        eligible_by_provider[prov] = eligible_qs.filter(
            source__provider_code=prov
        ).count()

    # Breakdown by age bucket (relative to start_time)
    cutoff_30 = start_time - timedelta(days=max(30, days))
    cutoff_60 = start_time - timedelta(days=60)

    bucket_21_to_30 = eligible_qs.filter(
        posted_at__gte=cutoff_30, posted_at__lt=cutoff_date
    ).count()
    bucket_31_to_60 = eligible_qs.filter(
        posted_at__gte=cutoff_60, posted_at__lt=cutoff_30
    ).count()
    bucket_60_plus = eligible_qs.filter(posted_at__lt=cutoff_60).count()

    eligible_by_age_bucket = {
        f"{days}_to_30_days": bucket_21_to_30,
        "31_to_60_days": bucket_31_to_60,
        "60_plus_days": bucket_60_plus,
    }

    deleted_count = 0
    failed_count = 0
    batches_processed = 0

    if execute and eligible_count > 0:
        logger.info(
            f"Executing cleanup: {eligible_count} eligible jobs from providers {sanitized_providers} "
            f"older than {cutoff_date.isoformat()} (batch_size={batch_size})"
        )

        while True:
            # Fetch primary keys of the next batch only to keep memory footprint minimal
            batch_ids = list(
                ExternalJob.objects.filter(
                    source__provider_code__in=sanitized_providers,
                    posted_at__lt=cutoff_date,
                ).values_list("id", flat=True)[:batch_size]
            )

            if not batch_ids:
                break

            try:
                with transaction.atomic():
                    num_deleted, _ = ExternalJob.objects.filter(
                        id__in=batch_ids
                    ).delete()
                    deleted_count += num_deleted
                    batches_processed += 1

                if sleep_between_batches > 0:
                    time.sleep(sleep_between_batches)

            except Exception as exc:
                failed_count += len(batch_ids)
                logger.error(
                    f"Failed to delete batch of {len(batch_ids)} external jobs: {exc}",
                    exc_info=True,
                )
                break

        # Reconcile ExternalJobSource active_jobs_count after deletions
        for source in ExternalJobSource.objects.filter(
            provider_code__in=sanitized_providers
        ):
            active_count = ExternalJob.objects.filter(
                source=source, is_active=True, status=ExternalJob.Status.ACTIVE
            ).count()
            source.active_jobs_count = active_count
            source.save(update_fields=["active_jobs_count"])

    duration_seconds = (timezone.now() - start_time).total_seconds()

    return {
        "dry_run": not execute,
        "days": days,
        "cutoff_date": cutoff_date.isoformat(),
        "target_providers": sanitized_providers,
        "scanned_count": scanned_count,
        "eligible_count": eligible_count,
        "deleted_count": deleted_count,
        "skipped_missing_date": skipped_missing_date_count,
        "skipped_fresh": skipped_fresh_count,
        "failed_count": failed_count,
        "batches_processed": batches_processed,
        "eligible_by_provider": eligible_by_provider,
        "eligible_by_age_bucket": eligible_by_age_bucket,
        "duration_seconds": round(duration_seconds, 3),
    }
