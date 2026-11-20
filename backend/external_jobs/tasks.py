import logging
from celery import shared_task
from django.utils import timezone
from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.cleanup import DEFAULT_RETENTION_DAYS, cleanup_external_jobs
from external_jobs.providers.people_prime import sync_people_prime_jobs
from external_jobs.providers.adzuna import sync_adzuna_jobs
from external_jobs.providers.himalayas import sync_himalayas_jobs

logger = logging.getLogger(__name__)


@shared_task(name="external_jobs.tasks.sync_people_prime_jobs_task")
def sync_people_prime_jobs_task():
    """
    Celery task to synchronize public jobs from People Prime ATS API.
    """
    logger.info("Executing People Prime ATS synchronization task...")
    return sync_people_prime_jobs()


@shared_task(name="external_jobs.tasks.sync_adzuna_jobs_task")
def sync_adzuna_jobs_task():
    """
    Celery task to synchronize public jobs from Adzuna API.
    """
    logger.info("Executing Adzuna synchronization task...")
    return sync_adzuna_jobs()


@shared_task(name="external_jobs.tasks.sync_himalayas_jobs_task")
def sync_himalayas_jobs_task(max_pages: int | None = None):
    """
    Celery task to synchronize public remote jobs from Himalayas Remote Jobs API.
    """
    logger.info("Executing Himalayas synchronization task...")
    return sync_himalayas_jobs(max_pages=max_pages)


@shared_task(bind=True, name="external_jobs.tasks.sync_external_jobs_task")
def sync_external_jobs_task(self, provider_code: str | None = None):
    """
    Master task for periodic synchronization of external jobs across enabled providers.
    """
    logger.info(f"Starting master external jobs sync task (provider_code={provider_code})...")

    sources = ExternalJobSource.objects.filter(api_enabled=True)
    if provider_code:
        sources = sources.filter(provider_code=provider_code)

    results = {}
    for source in sources:
        if source.provider_code == "people_prime":
            logger.info("Dispatching People Prime sync...")
            results[source.provider_code] = sync_people_prime_jobs()
        elif source.provider_code == "adzuna":
            logger.info("Dispatching Adzuna sync...")
            results[source.provider_code] = sync_adzuna_jobs()
        elif source.provider_code == "himalayas":
            logger.info("Dispatching Himalayas sync...")
            results[source.provider_code] = sync_himalayas_jobs()
        else:
            logger.info(f"Skipping placeholder provider: {source.name} ({source.provider_code})")
            results[source.provider_code] = {
                "status": "SKIPPED_PLACEHOLDER",
                "fetched": 0,
            }

    sync_result = {
        "status": "COMPLETED",
        "processed_sources": len(results),
        "details": results,
    }

    # Asynchronously dispatch incremental embedding generation for eligible missing external jobs
    try:
        from django.db import models
        from matching.tasks import generate_external_job_embeddings_batch_task
        from matching.models import EmbeddingStatus

        # Find eligible US remote jobs without completed embeddings (batch up to 500 per ingestion cycle)
        eligible_missing_ids = list(
            ExternalJob.objects.filter(
                is_active=True,
                status=ExternalJob.Status.ACTIVE,
                country="US",
                remote_type__in=[ExternalJob.RemoteType.REMOTE, ExternalJob.RemoteType.HYBRID],
            ).filter(
                models.Q(embedding_record__isnull=True)
                | models.Q(embedding_record__status=EmbeddingStatus.PENDING)
                | models.Q(embedding_record__embedding__isnull=True)
            ).values_list("id", flat=True)[:500]
        )

        if eligible_missing_ids:
            logger.info("Enqueuing embedding generation for %d newly ingested/unembedded external jobs.", len(eligible_missing_ids))
            for i in range(0, len(eligible_missing_ids), 50):
                chunk = [str(x) for x in eligible_missing_ids[i:i + 50]]
                generate_external_job_embeddings_batch_task.delay(chunk)
    except Exception as emb_dispatch_err:
        # Non-blocking: external job ingestion must NEVER fail because of embedding dispatch errors
        logger.error("Error scheduling incremental external job embedding tasks: %s", emb_dispatch_err)

    return sync_result


@shared_task(name="external_jobs.tasks.expire_stale_external_jobs_task")
def expire_stale_external_jobs_task():
    """
    Domain-isolated task to expire stale external jobs.
    Evaluates expiration dates without affecting internal People Remotely jobs.
    """
    now = timezone.now()
    expired_count = ExternalJob.objects.filter(
        status=ExternalJob.Status.ACTIVE,
        expires_at__lt=now
    ).update(status=ExternalJob.Status.EXPIRED, is_active=False)

    logger.info(f"Expired {expired_count} stale external jobs.")

    for source in ExternalJobSource.objects.all():
        active_count = ExternalJob.objects.filter(
            source=source, is_active=True, status=ExternalJob.Status.ACTIVE
        ).count()
        source.active_jobs_count = active_count
        source.save(update_fields=["active_jobs_count"])

    return {"expired_count": expired_count}


@shared_task(name="external_jobs.tasks.cleanup_external_jobs_task")
def cleanup_external_jobs_task(
    days: int = DEFAULT_RETENTION_DAYS, batch_size: int = 1000, execute: bool = False
):
    """
    Scheduled task to automatically delete stale external jobs from third-party aggregators
    ('adzuna', 'himalayas') whose original publication date (posted_at) is older than `days`.
    Preserves People Prime ATS jobs and employer-created jobs.
    """
    logger.info(
        f"Executing external jobs cleanup task (days={days}, batch_size={batch_size}, execute={execute})..."
    )


    return cleanup_external_jobs(days=days, batch_size=batch_size, execute=execute)
