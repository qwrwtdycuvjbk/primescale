from celery import shared_task
import logging
from .services import (
    run_hybrid_matching_for_candidate,
    run_hybrid_matching_for_job,
    run_matching_for_candidate,
    run_matching_for_job,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_matching_for_candidate_task(self, candidate_profile_id: str):
    """
    Asynchronous Celery task to run Phase 7 Hybrid Matching when a candidate profile is completed.
    Strictly uses hybrid matching; never falls back to legacy 2-component matching.
    """
    try:
        result = run_hybrid_matching_for_candidate(candidate_profile_id)
        logger.info(f"Hybrid matching for candidate {candidate_profile_id} completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error running hybrid matching for candidate {candidate_profile_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def run_matching_for_job_task(self, job_id: str):
    """
    Asynchronous Celery task to run Phase 7 Hybrid Matching when a new job is published.
    Strictly uses hybrid matching; never falls back to legacy 2-component matching.
    """
    try:
        result = run_hybrid_matching_for_job(job_id)
        logger.info(f"Hybrid matching for job {job_id} completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error running hybrid matching for job {job_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)

MAX_TASK_RETRY_DELAY: int = 300  # Cap maximum retry delay to 5 minutes


@shared_task(
    bind=True,
    max_retries=3,
    name="matching.tasks.generate_external_job_embedding_task",
)
def generate_external_job_embedding_task(self, external_job_id: str, force_regenerate: bool = False):
    """
    Asynchronous Celery task to generate embedding for a single eligible external job.
    Idempotent: skips API call if embedding is already completed and content hash matches.
    Bounded retries for transient errors only; permanent errors fail safely.
    """
    from matching.external_job_embeddings import ExternalJobEmbeddingService
    from common.embedding_client import EmbeddingRateLimitError, EmbeddingTransientError

    service = ExternalJobEmbeddingService()
    try:
        result = service.generate_embedding_for_job(
            external_job_id,
            force_regenerate=force_regenerate,
            raise_on_transient=True,
        )
        return {
            "external_job_id": str(external_job_id),
            "status": result.status.value,
            "is_unchanged": result.is_unchanged,
            "is_stale": result.is_stale,
            "dimensions": result.dimensions,
            "error": result.error_message,
        }
    except (EmbeddingTransientError, EmbeddingRateLimitError) as exc:
        raw_retry_after = getattr(exc, "retry_after", None)
        if raw_retry_after is not None and isinstance(raw_retry_after, (int, float)) and raw_retry_after > 0:
            countdown = min(int(raw_retry_after), MAX_TASK_RETRY_DELAY)
        else:
            countdown = min(2 ** self.request.retries * 5, MAX_TASK_RETRY_DELAY)

        logger.warning(
            "Transient error in generate_external_job_embedding_task for %s (attempt %d/3); retrying in %ds",
            external_job_id,
            self.request.retries + 1,
            countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error(
            "Permanent failure in generate_external_job_embedding_task for %s: %s",
            external_job_id,
            type(exc).__name__,
        )
        return {
            "external_job_id": str(external_job_id),
            "status": "failed",
            "error": type(exc).__name__,
        }


@shared_task(
    bind=True,
    name="matching.tasks.generate_external_job_embeddings_batch_task",
)
def generate_external_job_embeddings_batch_task(self, job_ids: list[str], force_regenerate: bool = False):
    """
    Processes a batch of external job IDs sequentially within a single worker task.
    Prevents worker queue overload while isolating per-job failures.
    """
    from matching.external_job_embeddings import ExternalJobEmbeddingService

    service = ExternalJobEmbeddingService()
    summary = {
        "total": len(job_ids),
        "completed": 0,
        "unchanged": 0,
        "failed": 0,
        "errors": {},
    }

    for jid in job_ids:
        try:
            res = service.generate_embedding_for_job(jid, force_regenerate=force_regenerate, raise_on_transient=False)
            if res.status.value == "completed":
                if res.is_unchanged:
                    summary["unchanged"] += 1
                else:
                    summary["completed"] += 1
            else:
                summary["failed"] += 1
                if res.error_message:
                    summary["errors"][str(jid)] = res.error_message
        except Exception as exc:
            summary["failed"] += 1
            summary["errors"][str(jid)] = type(exc).__name__
            logger.error("Error processing external job %s in batch: %s", jid, exc)

    logger.info("Batch external job embedding completed: %s", summary)

    # If any external job embeddings were newly completed in this batch, schedule bounded candidate reevaluation
    if summary["completed"] > 0:
        try:
            dispatch_external_job_candidate_reevaluation_task.delay()
        except Exception as exc:
            logger.warning("Could not trigger candidate reevaluation following external job embedding batch: %s", exc)

    return summary


@shared_task(
    bind=True,
    max_retries=3,
    name="matching.tasks.generate_resume_embedding_task",
)
def generate_resume_embedding_task(self, candidate_profile_id: str):
    """
    Asynchronous Celery task to generate embedding for a candidate's extracted resume text.
    Idempotent: skips API call if embedding is already up to date.
    Bounded retries for transient errors only; permanent errors fail immediately.
    Never returns or logs private text, vectors, or credentials.
    """
    from .resume_embeddings import ResumeEmbeddingService
    from common.embedding_client import EmbeddingRateLimitError, EmbeddingTransientError

    service = ResumeEmbeddingService()
    try:
        result = service.generate_embedding_for_candidate(
            candidate_profile_id,
            raise_on_transient=True,
        )
        return {
            "candidate_profile_id": str(candidate_profile_id),
            "status": result.status.value,
            "is_unchanged": result.is_unchanged,
            "is_stale": result.is_stale,
            "dimensions": result.dimensions,
            "error": result.error_message,
        }
    except (EmbeddingTransientError, EmbeddingRateLimitError) as exc:
        raw_retry_after = getattr(exc, "retry_after", None)
        if raw_retry_after is not None and isinstance(raw_retry_after, (int, float)) and raw_retry_after > 0:
            countdown = min(int(raw_retry_after), MAX_TASK_RETRY_DELAY)
        else:
            countdown = min(2 ** self.request.retries * 5, MAX_TASK_RETRY_DELAY)

        logger.warning(
            "Transient error in generate_resume_embedding_task for %s (attempt %d/3); retrying in %ds",
            candidate_profile_id,
            self.request.retries + 1,
            countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error(
            "Permanent failure in generate_resume_embedding_task for %s: %s",
            candidate_profile_id,
            type(exc).__name__,
        )
        return {
            "candidate_profile_id": str(candidate_profile_id),
            "status": "failed",
            "error": type(exc).__name__,
        }


@shared_task(
    bind=True,
    max_retries=3,
    name="matching.tasks.process_candidate_resume_task",
)
def process_candidate_resume_task(
    self,
    candidate_profile_id: str,
    expected_resume_path: str = None,
):
    """
    End-to-end asynchronous Celery task for candidate resume lifecycle:
    1. Verifies candidate profile and checks against expected resume path (stale protection).
    2. Securely extracts normalized text from private storage and persists it to CandidateResumeEmbedding.
    3. Generates 2,048-dimensional passage embedding via NvidiaEmbeddingClient.
    4. Evaluates candidate eligibility (open_to_matching and profile_complete).
    5. If eligible, asynchronously dispatches hybrid matching task.
    """
    from candidates.models import CandidateProfile
    from common.embedding_client import EmbeddingRateLimitError, EmbeddingTransientError
    from common.resume_extraction import ResumeTextExtractionService
    from .resume_embeddings import ResumeEmbeddingService

    # 1. Fetch CandidateProfile
    try:
        profile = CandidateProfile.objects.select_related("user").get(id=candidate_profile_id)
    except (CandidateProfile.DoesNotExist, ValueError):
        logger.warning("Candidate profile %s not found; aborting resume task.", candidate_profile_id)
        return {"status": "candidate_not_found", "candidate_profile_id": str(candidate_profile_id)}

    profile_id_str = str(profile.id)

    # Stale task protection: check if current resume_url matches expected_resume_path
    if not profile.resume_url:
        logger.info("Candidate %s has no resume_url; aborting resume task.", profile_id_str)
        return {"status": "no_resume", "candidate_profile_id": profile_id_str}

    if expected_resume_path and profile.resume_url != expected_resume_path:
        logger.warning(
            "Resume path for candidate %s changed (expected %s, found %s); discarding stale task.",
            profile_id_str,
            expected_resume_path,
            profile.resume_url,
        )
        return {"status": "stale_resume_discarded", "candidate_profile_id": profile_id_str}

    # 2. Extract and Persist Resume Text
    extraction_service = ResumeTextExtractionService()
    extraction_result = extraction_service.extract_and_persist_for_candidate(profile)

    if not extraction_result.is_success:
        logger.warning(
            "Resume text extraction failed for candidate %s: %s (%s)",
            profile_id_str,
            extraction_result.error_message,
            extraction_result.status.value,
        )
        return {
            "status": "extraction_failed",
            "candidate_profile_id": profile_id_str,
            "error": extraction_result.error_message,
            "extraction_status": extraction_result.status.value,
        }

    # Re-check profile state after extraction before calling external embedding API
    profile.refresh_from_db(fields=["resume_url", "open_to_matching", "profile_complete"])
    if expected_resume_path and profile.resume_url != expected_resume_path:
        logger.warning(
            "Resume path for candidate %s changed during extraction; discarding stale task.",
            profile_id_str,
        )
        return {"status": "stale_resume_discarded", "candidate_profile_id": profile_id_str}

    # 3. Generate Embedding Vector
    embedding_service = ResumeEmbeddingService()
    try:
        embedding_result = embedding_service.generate_embedding_for_candidate(
            profile,
            raise_on_transient=True,
        )
    except (EmbeddingTransientError, EmbeddingRateLimitError) as exc:
        raw_retry_after = getattr(exc, "retry_after", None)
        if raw_retry_after is not None and isinstance(raw_retry_after, (int, float)) and raw_retry_after > 0:
            countdown = min(int(raw_retry_after), MAX_TASK_RETRY_DELAY)
        else:
            countdown = min(2 ** self.request.retries * 5, MAX_TASK_RETRY_DELAY)

        logger.warning(
            "Transient error in process_candidate_resume_task for %s (attempt %d/3); retrying in %ds",
            profile_id_str,
            self.request.retries + 1,
            countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error(
            "Permanent failure in process_candidate_resume_task for %s: %s",
            profile_id_str,
            type(exc).__name__,
        )
        return {
            "status": "embedding_failed",
            "candidate_profile_id": profile_id_str,
            "error": type(exc).__name__,
        }

    if not embedding_result.is_success or embedding_result.is_stale:
        return {
            "status": "stale_embedding_discarded" if embedding_result.is_stale else "embedding_failed",
            "candidate_profile_id": profile_id_str,
            "error": embedding_result.error_message,
            "is_stale": embedding_result.is_stale,
        }

    # 4. Check eligibility & trigger hybrid matching
    profile.refresh_from_db(fields=["open_to_matching", "profile_complete", "profile_completeness", "resume_url"])
    is_eligible = profile.open_to_matching and profile.profile_complete and getattr(profile, "profile_completeness", 0) == 100 and bool(profile.resume_url)

    if is_eligible:
        run_matching_for_candidate_task.delay(profile_id_str)
        evaluate_candidate_external_recommendations_task.delay(profile_id_str)
        matching_scheduled = True
        logger.info(
            "First-party matching and external recommendations tasks enqueued for candidate %s",
            profile_id_str,
        )
    else:
        matching_scheduled = False
        logger.info(
            "Candidate %s not eligible for immediate matching (open=%s, complete=%s, completeness=%s)",
            profile_id_str,
            profile.open_to_matching,
            profile.profile_complete, getattr(profile, "profile_completeness", None),
        )

    return {
        "status": "completed",
        "candidate_profile_id": profile_id_str,
        "is_unchanged": embedding_result.is_unchanged,
        "is_stale": embedding_result.is_stale,
        "dimensions": embedding_result.dimensions,
        "matching_scheduled": matching_scheduled,
    }


@shared_task(
    bind=True,
    max_retries=3,
    name="matching.tasks.generate_job_embedding_task",
)
def generate_job_embedding_task(self, job_id: str):
    """
    Asynchronous Celery task to generate embedding for an eligible first-party Job.
    Idempotent: skips API call if embedding is already up to date.
    Bounded retries for transient errors only; permanent errors fail immediately.
    Never returns or logs private text, vectors, or credentials.
    Chains to run_matching_for_job_task upon successful, non-stale embedding generation
    for an eligible active job.
    """
    from .job_embeddings import (
        JobEmbeddingService,
        JobTextPreparationService,
        is_eligible_first_party_job,
    )
    from .models import TARGET_EMBEDDING_DIMENSIONS, EmbeddingStatus
    from common.embedding_client import EmbeddingRateLimitError, EmbeddingTransientError
    from jobs.models import Job

    service = JobEmbeddingService()
    try:
        result = service.generate_embedding_for_job(
            job_id,
            raise_on_transient=True,
        )
    except (EmbeddingTransientError, EmbeddingRateLimitError) as exc:
        raw_retry_after = getattr(exc, "retry_after", None)
        if raw_retry_after is not None and isinstance(raw_retry_after, (int, float)) and raw_retry_after > 0:
            countdown = min(int(raw_retry_after), MAX_TASK_RETRY_DELAY)
        else:
            countdown = min(2 ** self.request.retries * 5, MAX_TASK_RETRY_DELAY)

        logger.warning(
            "Transient error in generate_job_embedding_task for %s (attempt %d/3); retrying in %ds",
            job_id,
            self.request.retries + 1,
            countdown,
        )
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.error(
            "Permanent failure in generate_job_embedding_task for %s: %s",
            job_id,
            type(exc).__name__,
        )
        return {
            "job_id": str(job_id),
            "status": "failed",
            "error": type(exc).__name__,
        }

    matching_scheduled = False
    if result.is_success and not result.is_stale:
        try:
            job = Job.objects.select_related("company", "posted_by", "job_embedding").get(id=job_id)
            is_eligible, ineligibility_reason = is_eligible_first_party_job(job)
            if not is_eligible:
                logger.info(
                    "Job %s is no longer eligible after embedding (%s); matching not scheduled",
                    job_id,
                    ineligibility_reason,
                )
            else:
                job_emb = getattr(job, "job_embedding", None)
                if (
                    not job_emb
                    or job_emb.status != EmbeddingStatus.COMPLETED
                    or not job_emb.embedding
                    or len(job_emb.embedding) != TARGET_EMBEDDING_DIMENSIONS
                ):
                    logger.warning(
                        "Job %s embedding is missing, incomplete, or invalid dimension; matching not scheduled",
                        job_id,
                    )
                else:
                    # Verify embedding corresponds to current job content
                    prepared = JobTextPreparationService.prepare_text(job)
                    if not prepared.is_eligible or job_emb.content_hash != prepared.content_hash:
                        logger.warning(
                            "Job %s embedding content hash mismatch; discarding matching trigger",
                            job_id,
                        )
                    else:
                        run_matching_for_job_task.delay(str(job_id))
                        matching_scheduled = True
                        logger.info("Hybrid matching task enqueued for job %s", job_id)
        except Job.DoesNotExist:
            logger.warning("Job %s not found when attempting to schedule matching", job_id)

    return {
        "job_id": str(job_id),
        "status": result.status.value,
        "is_unchanged": result.is_unchanged,
        "is_stale": result.is_stale,
        "dimensions": result.dimensions,
        "matching_scheduled": matching_scheduled,
        "error": result.error_message,
    }


@shared_task(
    bind=True,
    max_retries=1,
    name="matching.tasks.notify_recruiter_high_match_task",
)
def notify_recruiter_high_match_task(self, match_id: str):
    """
    Retired legacy Celery task for high-match notifications (Phase 9.10).
    Retained to safely reconcile any legacy messages currently in broker queues.

    Conservative handling:
    - Never calls send_mail().
    - If a corresponding outbox row exists:
        Does not send an email and does not create another outbox row.
    - If no outbox row exists:
        Does NOT automatically enqueue an email (to prevent duplicating a previously
        sent legacy email). Instead, records an outbox record with status PERMANENTLY_FAILED
        and a clear, sanitized manual-review reason.
    - Match.recruiter_notified_at is NOT treated as proof of delivery.
    """
    from django.conf import settings
    from django.db import IntegrityError, transaction
    from matching.models import Match
    from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType

    try:
        match = Match.objects.select_related("job", "job__company", "candidate_profile").get(id=match_id)
    except (Match.DoesNotExist, ValueError):
        logger.warning("Legacy task called for non-existent match %s; safely aborting.", match_id)
        return {"delivered": False, "status": "match_not_found", "match_id": str(match_id)}

    # 1. Check if corresponding outbox row already exists
    existing_outbox = NotificationOutbox.objects.filter(
        match=match,
        notification_type=NotificationType.HIGH_MATCH_ALERT,
    ).first()

    if existing_outbox:
        logger.info(
            "Legacy task reconciliation: outbox row already exists for match %s (status=%s). "
            "No email sent or enqueued.",
            match_id,
            existing_outbox.status,
        )
        return {
            "delivered": False,
            "status": "outbox_already_exists",
            "outbox_status": existing_outbox.status,
            "match_id": str(match_id),
            "outbox_id": str(existing_outbox.id),
        }

    # 2. If no outbox row exists, do NOT automatically enqueue an email.
    # Record a clear, sanitized manual-review signal using existing schema (PERMANENTLY_FAILED).
    # Does not fabricate provider acceptance or confirmed delivery.
    company_name = match.job.company.name if (match.job and match.job.company) else ""
    job_title = match.job.title if match.job else "Role"
    recipient_email = getattr(settings, "PEOPLE_PRIME_HANDOFF_EMAIL", "remote@people-prime.com")
    subject = f"[High Match Alert] {match.match_score}% Match: {job_title} at {company_name or 'Company'}"
    idempotency_key = f"match:{match.id}:{NotificationType.HIGH_MATCH_ALERT}"

    review_reason = (
        "Legacy task reconciliation: delivery status unknown. An alert may have been sent "
        "via legacy Phase 8 send_mail or dropped. Automated delivery halted to prevent duplicate "
        "email; flagged for manual review."
    )

    payload = {
        "match_id": str(match.id),
        "job_id": str(match.job.id) if match.job else "",
        "job_title": job_title,
        "company_name": company_name,
        "final_score": int(match.match_score),
        "raw_final_score": float(match.match_score),
        "manual_review_required": True,
        "reconciliation_source": "legacy_celery_task",
    }

    try:
        with transaction.atomic():
            outbox_record = NotificationOutbox.objects.create(
                match=match,
                notification_type=NotificationType.HIGH_MATCH_ALERT,
                idempotency_key=idempotency_key,
                status=DeliveryStatus.PERMANENTLY_FAILED,
                recipient_email=recipient_email,
                subject=subject,
                payload=payload,
                last_error=review_reason,
                retry_count=0,
                max_retries=0,
                provider_message_id=None,
                delivered_at=None,
            )
            logger.warning(
                "Legacy task reconciliation: recorded manual-review outbox record %s for match %s "
                "with status=PERMANENTLY_FAILED. No email dispatched.",
                outbox_record.id,
                match_id,
            )
            return {
                "delivered": False,
                "status": "manual_review_required",
                "match_id": str(match_id),
                "outbox_id": str(outbox_record.id),
                "reason": review_reason,
            }
    except IntegrityError:
        existing = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).first()
        return {
            "delivered": False,
            "status": "outbox_already_exists",
            "outbox_status": existing.status if existing else "unknown",
            "match_id": str(match_id),
        }


@shared_task(
    bind=True,
    max_retries=3,
    name="matching.tasks.evaluate_candidate_external_recommendations_task",
)
def evaluate_candidate_external_recommendations_task(
    self,
    candidate_profile_id: str,
    retrieval_limit: int = 100,
    force_recalculate: bool = False,
):
    """
    Celery task to evaluate eligible external jobs against a candidate's profile and resume embedding,
    persisting recommendations scoring >= 70.0% into ExternalJobRecommendation.
    Uses Redis cache locking for concurrency control / idempotency.
    """
    import redis
    from django.core.cache import cache
    from backend.matching.external_recommendations import CandidateExternalRecommendationService

    lock_key = f"lock:evaluate_candidate_external_recommendations:{candidate_profile_id}"
    # Acquire non-blocking lock with 5-minute timeout
    lock_acquired = cache.add(lock_key, "locked", timeout=300)
    if not lock_acquired:
        logger.warning(
            "Evaluation for candidate %s is already running. Skipping duplicate task invocation.",
            candidate_profile_id,
        )
        return {
            "candidate_profile_id": candidate_profile_id,
            "status": "skipped",
            "reason": "concurrent_execution_locked",
        }

    try:
        service = CandidateExternalRecommendationService()
        result = service.evaluate_candidate(
            candidate_or_id=candidate_profile_id,
            retrieval_limit=retrieval_limit,
            force_recalculate=force_recalculate,
        )
        logger.info(
            "Evaluated external recommendations for candidate %s: evaluated=%d, qualified=%d, updated=%d, pruned=%d",
            candidate_profile_id,
            result.total_evaluated,
            result.qualified_count,
            result.updated_count,
            result.pruned_count,
        )
        return {
            "candidate_profile_id": result.candidate_profile_id,
            "total_evaluated": result.total_evaluated,
            "qualified_count": result.qualified_count,
            "updated_count": result.updated_count,
            "pruned_count": result.pruned_count,
            "is_eligible": result.is_eligible,
            "ineligibility_reason": result.ineligibility_reason,
            "status": "completed" if result.is_eligible else "ineligible",
        }
    except Exception as exc:
        logger.error(
            "Error evaluating external recommendations for candidate %s: %s",
            candidate_profile_id,
            exc,
            exc_info=True,
        )
        # Exponential backoff retry
        retry_delay = min(60 * (2 ** self.request.retries), MAX_TASK_RETRY_DELAY)
        raise self.retry(exc=exc, countdown=retry_delay)
    finally:
        try:
            cache.delete(lock_key)
        except Exception as e:
            logger.warning("Failed to release lock %s: %s", lock_key, e)


@shared_task(
    bind=True,
    max_retries=2,
    name="matching.tasks.dispatch_external_job_candidate_reevaluation_task",
)
def dispatch_external_job_candidate_reevaluation_task(
    self,
    chunk_size: int = 50,
    max_candidates: int = 500,
):
    """
    Bounded background task to trigger external recommendation evaluations for eligible candidates
    when external job embeddings are completed or updated.

    Architecture & Safeguards:
    1. Distributed Lock: Uses a Redis cache lock ('lock:dispatch_external_job_reevaluation')
       with a 10-minute cooldown to prevent concurrent or rapid-fire fan-out.
    2. Candidate Eligibility Filter: Evaluates ONLY candidates with:
       - user.is_active = True
       - profile_completeness = 100
       - profile_complete = True
       - open_to_matching = True
       - non-empty resume_url
       - CandidateResumeEmbedding.status = 'completed' with valid 2048-dim vector.
    3. Bounded Chunking: Processes eligible candidates in chunks (default 50) up to a max cap
       (default 500 candidates per run), dispatching evaluate_candidate_external_recommendations_task
       asynchronously with independent per-candidate locks.
    4. Non-blocking to Ingestion: Never blocks external job API ingestion or batch embedding tasks.
    """
    from django.core.cache import cache
    from candidates.models import CandidateProfile
    from matching.models import CandidateResumeEmbedding, EmbeddingStatus, TARGET_EMBEDDING_DIMENSIONS

    lock_key = "lock:dispatch_external_job_reevaluation"
    # Acquire non-blocking cooldown lock (10 minutes)
    lock_acquired = cache.add(lock_key, "locked", timeout=600)
    if not lock_acquired:
        logger.info("External job candidate reevaluation is already queued or ran recently. Skipping duplicate dispatch.")
        return {
            "status": "skipped",
            "reason": "rate_limited_or_running",
        }

    try:
        # Query fully eligible candidates with completed, valid vectors
        eligible_candidates_qs = (
            CandidateProfile.objects.filter(
                user__is_active=True,
                profile_completeness=100,
                profile_complete=True,
                open_to_matching=True,
                resume_embedding__status=EmbeddingStatus.COMPLETED,
            )
            .exclude(resume_url__isnull=True)
            .exclude(resume_url="")
            .values_list("id", flat=True)
            .order_by("-updated_at")[:max_candidates]
        )

        candidate_ids = [str(cid) for cid in eligible_candidates_qs]
        total_eligible = len(candidate_ids)

        if total_eligible == 0:
            logger.info("No eligible candidates with completed resume embeddings found for external job reevaluation.")
            return {
                "status": "completed",
                "dispatched_count": 0,
                "reason": "no_eligible_candidates",
            }

        # Dispatch in bounded chunks
        dispatched_count = 0
        for i in range(0, total_eligible, chunk_size):
            chunk = candidate_ids[i : i + chunk_size]
            for cid in chunk:
                evaluate_candidate_external_recommendations_task.delay(cid)
                dispatched_count += 1

        logger.info(
            "Dispatched external recommendation evaluations for %d eligible candidates (chunk_size=%d).",
            dispatched_count,
            chunk_size,
        )
        return {
            "status": "completed",
            "dispatched_count": dispatched_count,
            "total_eligible_found": total_eligible,
        }
    except Exception as exc:
        logger.error("Error in dispatch_external_job_candidate_reevaluation_task: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60)
