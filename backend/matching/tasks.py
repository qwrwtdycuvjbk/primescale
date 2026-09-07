from celery import shared_task
import logging
from .services import run_matching_for_candidate, run_matching_for_job

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_matching_for_candidate_task(self, candidate_profile_id: str):
    """
    Asynchronous Celery task to run matching when a candidate profile is completed.
    """
    try:
        result = run_matching_for_candidate(candidate_profile_id)
        logger.info(f"Matching for candidate {candidate_profile_id} completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error running matching for candidate {candidate_profile_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def run_matching_for_job_task(self, job_id: str):
    """
    Asynchronous Celery task to run matching when a new job is published.
    """
    try:
        result = run_matching_for_job(job_id)
        logger.info(f"Matching for job {job_id} completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error running matching for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
