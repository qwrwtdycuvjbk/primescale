import logging
import uuid
from django.db.models.signals import post_delete, post_init, post_save
from django.dispatch import receiver
from candidates.models import CandidateProfile
from jobs.models import Job
from matching.models import EmbeddingStatus, JobEmbedding

logger = logging.getLogger(__name__)


@receiver(post_init, sender=Job)
def record_job_initial_state(sender, instance: Job, **kwargs):
    """
    Records initial field values on model instance initialization.
    Used in post_save to detect status transitions and material content changes.
    """
    instance._initial_status = instance.status
    instance._initial_title = instance.title
    instance._initial_description = instance.description
    instance._initial_role_type = instance.role_type
    instance._initial_experience_level = instance.experience_level
    if isinstance(instance.tech_stack, list):
        instance._initial_tech_stack = list(instance.tech_stack)
    elif isinstance(instance.tech_stack, dict):
        instance._initial_tech_stack = dict(instance.tech_stack)
    else:
        instance._initial_tech_stack = instance.tech_stack
    instance._initial_work_type = instance.work_type
    instance._initial_visa_requirements = instance.visa_requirements
    instance._initial_company_id = instance.company_id
    instance._initial_posted_by_id = instance.posted_by_id
    instance._initial_expires_at = instance.expires_at


def _update_job_initial_state(instance: Job) -> None:
    instance._initial_status = instance.status
    instance._initial_title = instance.title
    instance._initial_description = instance.description
    instance._initial_role_type = instance.role_type
    instance._initial_experience_level = instance.experience_level
    if isinstance(instance.tech_stack, list):
        instance._initial_tech_stack = list(instance.tech_stack)
    elif isinstance(instance.tech_stack, dict):
        instance._initial_tech_stack = dict(instance.tech_stack)
    else:
        instance._initial_tech_stack = instance.tech_stack
    instance._initial_work_type = instance.work_type
    instance._initial_visa_requirements = instance.visa_requirements
    instance._initial_company_id = instance.company_id
    instance._initial_posted_by_id = instance.posted_by_id
    instance._initial_expires_at = instance.expires_at


@receiver(post_save, sender=Job)
def handle_job_post_save(sender, instance: Job, created: bool, **kwargs):
    """
    First-party employer job lifecycle pipeline orchestration:
    1. Creation of an active, eligible first-party job:
       Enqueues generate_job_embedding_task via transaction.on_commit().
    2. Transition to inactive (paused, closed, archived, etc.):
       Immediately invalidates any existing JobEmbedding (clearing vector, version bumped).
       Does NOT mass-delete existing matches.
    3. Transition from inactive (draft, paused, closed) to active:
       If eligible, enqueues generate_job_embedding_task via transaction.on_commit().
    4. Material content change on an active job:
       If material fields (title, description, role_type, experience_level, tech_stack,
       work_type, visa_requirements, company) changed:
       Invalidates stale completed embedding and enqueues generate_job_embedding_task via transaction.on_commit().
    5. Non-material changes (salary_range, featured, quality score/feedback):
       Strictly ignores and does NOT enqueue tasks.
    """
    from django.db import transaction
    from matching.job_embeddings import (
        JobTextPreparationService,
        invalidate_job_embedding,
        is_eligible_first_party_job,
    )
    from matching.models import EmbeddingStatus, JobEmbedding
    from matching.tasks import generate_job_embedding_task

    initial_status = getattr(instance, "_initial_status", None)
    current_status = instance.status
    job_id_str = str(instance.id)

    def schedule_embedding(j_id=job_id_str):
        generate_job_embedding_task.delay(j_id)

    # 1. New Job Creation
    if created:
        if current_status == Job.Status.ACTIVE:
            is_eligible, reason = is_eligible_first_party_job(instance)
            if is_eligible:
                transaction.on_commit(schedule_embedding)
                logger.info("Enqueued job embedding for newly created active job %s", job_id_str)
            else:
                logger.info("Created active job %s is not eligible for embedding: %s", job_id_str, reason)
        _update_job_initial_state(instance)
        return

    # 2. Existing Job - Deactivation (transition from ACTIVE to non-ACTIVE)
    if initial_status == Job.Status.ACTIVE and current_status != Job.Status.ACTIVE:
        invalidate_job_embedding(
            instance,
            reason=f"Job status changed from '{initial_status}' to '{current_status}'.",
        )
        logger.info(
            "Invalidated embedding for deactivated job %s (status=%s)",
            job_id_str,
            current_status,
        )
        _update_job_initial_state(instance)
        return

    # 3. Existing Job - Activation / Reactivation (transition from non-ACTIVE to ACTIVE)
    if initial_status != Job.Status.ACTIVE and current_status == Job.Status.ACTIVE:
        is_eligible, reason = is_eligible_first_party_job(instance)
        if is_eligible:
            transaction.on_commit(schedule_embedding)
            logger.info("Enqueued job embedding for reactivated job %s", job_id_str)
        else:
            logger.info("Reactivated job %s is not eligible for embedding: %s", job_id_str, reason)
        _update_job_initial_state(instance)
        return

    # 4. If current status is not ACTIVE (e.g. DRAFT or PAUSED edited while inactive)
    if current_status != Job.Status.ACTIVE:
        _update_job_initial_state(instance)
        return

    # 5. Existing Job is ACTIVE and remains ACTIVE: Check for material content changes
    initial_title = getattr(instance, "_initial_title", None)
    initial_desc = getattr(instance, "_initial_description", None)
    initial_role = getattr(instance, "_initial_role_type", None)
    initial_exp = getattr(instance, "_initial_experience_level", None)
    initial_stack = getattr(instance, "_initial_tech_stack", None)
    initial_work = getattr(instance, "_initial_work_type", None)
    initial_visa = getattr(instance, "_initial_visa_requirements", None)
    initial_company = getattr(instance, "_initial_company_id", None)

    material_fields_changed = (
        initial_title is not None and (
            initial_title != instance.title
            or initial_desc != instance.description
            or initial_role != instance.role_type
            or initial_exp != instance.experience_level
            or initial_stack != instance.tech_stack
            or initial_work != instance.work_type
            or initial_visa != instance.visa_requirements
            or initial_company != instance.company_id
        )
    )

    if material_fields_changed:
        is_eligible, reason = is_eligible_first_party_job(instance)
        if is_eligible:
            prepared = JobTextPreparationService.prepare_text(instance)
            existing_emb = JobEmbedding.objects.filter(job=instance).first()
            if existing_emb and existing_emb.status == EmbeddingStatus.COMPLETED and existing_emb.content_hash == prepared.content_hash:
                logger.info("Material fields edited on job %s but content_hash is identical; skipping embedding", job_id_str)
            else:
                if existing_emb and existing_emb.status == EmbeddingStatus.COMPLETED:
                    JobEmbedding.objects.filter(job=instance, status=EmbeddingStatus.COMPLETED).update(
                        status=EmbeddingStatus.PENDING,
                        embedding=None,
                        embedded_at=None,
                        version=uuid.uuid4().hex[:16],
                    )
                transaction.on_commit(schedule_embedding)
                logger.info("Enqueued job embedding for material edit on active job %s", job_id_str)
        else:
            invalidate_job_embedding(instance, reason=reason)
            logger.info("Active job %s became ineligible upon edit: %s", job_id_str, reason)
    elif initial_title is None:
        is_eligible, reason = is_eligible_first_party_job(instance)
        if is_eligible:
            prepared = JobTextPreparationService.prepare_text(instance)
            existing_emb = JobEmbedding.objects.filter(job=instance).first()
            if not existing_emb or existing_emb.content_hash != prepared.content_hash:
                transaction.on_commit(schedule_embedding)
                logger.info("Enqueued job embedding for job %s (no initial state recorded)", job_id_str)

    _update_job_initial_state(instance)


@receiver(post_delete, sender=Job)
def handle_job_post_delete(sender, instance: Job, **kwargs):
    """
    Cleans up any orphaned JobEmbedding records if not already cascade-deleted.
    """
    from matching.models import JobEmbedding
    JobEmbedding.objects.filter(job=instance).delete()


@receiver(post_init, sender=CandidateProfile)
def record_candidate_profile_initial_state(sender, instance: CandidateProfile, **kwargs):
    """
    Records initial field values on model instance initialization.
    Used in post_save to detect whether resume_url or eligibility flags changed.
    """
    instance._initial_resume_url = instance.__dict__.get("resume_url")
    instance._initial_open_to_matching = instance.__dict__.get("open_to_matching")
    instance._initial_profile_complete = instance.__dict__.get("profile_complete")
    instance._initial_profile_completeness = instance.__dict__.get("profile_completeness", 0)


@receiver(post_save, sender=CandidateProfile)
def handle_candidate_profile_post_save(sender, instance: CandidateProfile, created: bool, **kwargs):
    """
    Candidate resume lifecycle pipeline orchestration:
    1. If resume_url changed to a non-empty path:
       Enqueues process_candidate_resume_task via transaction.on_commit().
    2. If resume_url was cleared (became None/empty):
       Invalidates any existing CandidateResumeEmbedding record.
    3. If resume_url did NOT change, but candidate became eligible (open_to_matching & profile_complete):
       If a completed, valid resume embedding exists, enqueues run_matching_for_candidate_task
       via transaction.on_commit().
    """
    from django.db import transaction
    from common.resume_extraction import calculate_source_fingerprint
    from matching.models import CandidateResumeEmbedding, EmbeddingStatus
    from matching.tasks import process_candidate_resume_task, run_matching_for_candidate_task

    initial_resume_url = getattr(instance, "_initial_resume_url", None)
    current_resume_url = instance.resume_url

    initial_open = getattr(instance, "_initial_open_to_matching", False)
    current_open = instance.open_to_matching

    initial_complete = getattr(instance, "_initial_profile_complete", False)
    current_complete = instance.profile_complete

    initial_completeness = getattr(instance, "_initial_profile_completeness", 0)
    current_completeness = getattr(instance, "profile_completeness", 0)

    # Determine if resume_url changed
    if created:
        resume_changed = bool(current_resume_url)
    elif hasattr(instance, "_initial_resume_url") and instance._initial_resume_url is not None:
        resume_changed = (instance._initial_resume_url != current_resume_url)
    elif current_resume_url:
        # Fallback when _initial_resume_url was not recorded: compare fingerprint with embedding
        expected_fp = calculate_source_fingerprint(current_resume_url)
        emb = CandidateResumeEmbedding.objects.filter(candidate_profile=instance).first()
        resume_changed = (emb is None or emb.version != expected_fp)
    else:
        resume_changed = False

    profile_id_str = str(instance.id)

    # 1. Resume uploaded or replaced
    if resume_changed and current_resume_url:
        def enqueue_processing(p_id=profile_id_str, r_url=current_resume_url):
            process_candidate_resume_task.delay(p_id, expected_resume_path=r_url)

        transaction.on_commit(enqueue_processing)
        logger.info("Enqueued resume processing for candidate %s (resume_url=%s)", profile_id_str, current_resume_url)

    # 2. Resume cleared
    elif (initial_resume_url and not current_resume_url) or (not current_resume_url and resume_changed):
        updated = CandidateResumeEmbedding.objects.filter(
            candidate_profile=instance,
        ).update(
            status=EmbeddingStatus.FAILED,
            error_message="Candidate resume was removed.",
            extracted_text=None,
            embedding=None,
            content_hash=None,
            version="",
        )
        if updated:
            logger.info("Invalidated resume embedding for candidate %s because resume was removed", profile_id_str)

    # 3. Eligibility transition without resume change
    elif not resume_changed and current_resume_url:
        became_eligible = (
            (not initial_open or not initial_complete or initial_completeness != 100)
            and (current_open and current_complete and current_completeness == 100)
        )
        if became_eligible:
            expected_fp = calculate_source_fingerprint(current_resume_url)
            emb = CandidateResumeEmbedding.objects.filter(
                candidate_profile=instance,
                status=EmbeddingStatus.COMPLETED,
                embedding__isnull=False,
                version=expected_fp,
            ).first()
            if emb:
                def enqueue_matching(p_id=profile_id_str):
                    run_matching_for_candidate_task.delay(p_id)

                transaction.on_commit(enqueue_matching)
                logger.info(
                    "Candidate %s became eligible with existing valid embedding; enqueued matching",
                    profile_id_str,
                )

    # Update in-memory tracking attributes
    instance._initial_resume_url = current_resume_url
    instance._initial_open_to_matching = current_open
    instance._initial_profile_complete = current_complete
    instance._initial_profile_completeness = current_completeness


@receiver(post_delete, sender=CandidateProfile)
def handle_candidate_profile_post_delete(sender, instance: CandidateProfile, **kwargs):
    """
    Cleans up any orphaned CandidateResumeEmbedding records if not already cascade-deleted.
    """
    from matching.models import CandidateResumeEmbedding
    CandidateResumeEmbedding.objects.filter(candidate_profile=instance).delete()
