import logging
from celery import shared_task
from django.utils import timezone
from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.providers.people_prime import sync_people_prime_jobs

logger = logging.getLogger(__name__)


@shared_task(name="external_jobs.tasks.sync_people_prime_jobs_task")
def sync_people_prime_jobs_task():
    """
    Celery task to synchronize public jobs from People Prime ATS API.
    """
    logger.info("Executing People Prime ATS synchronization task...")
    return sync_people_prime_jobs()


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
        else:
            logger.info(f"Skipping placeholder provider: {source.name} ({source.provider_code})")
            results[source.provider_code] = {
                "status": "SKIPPED_PLACEHOLDER",
                "fetched": 0,
            }

    return {
        "status": "COMPLETED",
        "processed_sources": len(results),
        "details": results,
    }


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
