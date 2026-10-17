"""
Job Description Normalization and Embedding Generation Foundation for PeopleRemotely AI Matching.

Features:
- Dedicated, testable service for preparing normalized job description text (JobTextPreparationService).
- Dedicated service for generating dense 2,048-dimensional passage embeddings for eligible jobs (JobEmbeddingService).
- Strict first-party job eligibility enforcement: explicitly excludes ExternalJob (Adzuna, Himalayas, People Prime ATS, etc.)
  and inactive, draft, paused, closed, archived, or expired jobs.
- Deterministic text preparation from stable, documented fields; strictly excludes pay rates, quality scores, credentials.
- Bounded input text (up to 16,000 characters) as a client-side character boundary (not a guaranteed token limit;
  actual token counts vary based on text vocabulary and density; input-too-long 422 errors are treated as permanent).
- Content-hash and generation-identifier idempotency to avoid redundant NVIDIA API calls.
- Concurrency & stale overwrite protection using select_for_update(), generation identifier, and updated_at re-checks.
  Guarantees that a stale task cannot overwrite a newer embedding or mark a newer successful embedding as failed.
- Both write-time invalidation (signals & explicit helper) and read-time filtering (get_eligible_job_embeddings).
- Distinguishes retryable transient errors from non-retryable permanent errors.
- Strictly private: never logs or leaks job embeddings, raw vectors, credentials, or internal metadata.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Any, Final

from django.db import models, transaction
from django.utils import timezone

from common.embedding_client import (
    MAX_INPUT_CHARACTERS,
    EmbeddingAuthenticationError,
    EmbeddingClientError,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingPermanentError,
    EmbeddingRateLimitError,
    EmbeddingResponseError,
    EmbeddingTransientError,
    EmbeddingValidationError,
    NvidiaEmbeddingClient,
)
from common.resume_extraction import calculate_content_hash, normalize_extracted_text
from jobs.models import Job
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    EmbeddingStatus,
    JobEmbedding,
)

logger = logging.getLogger(__name__)


def is_eligible_first_party_job(job: Any) -> tuple[bool, str | None]:
    """
    Verifies if a job is an eligible first-party PeopleRemotely employer job.
    Explicitly excludes ExternalJob (Adzuna, Himalayas, People Prime, etc.) and
    inactive, draft, paused, closed, archived, or expired jobs.
    """
    if not isinstance(job, Job):
        return False, "Object is not an instance of first-party Job model."

    # Must be linked to a registered Company and Employer User
    if not getattr(job, "company_id", None):
        return False, "Job is not associated with an employer Company."

    if not getattr(job, "posted_by_id", None):
        return False, "Job is not associated with an employer User."

    # Status check: only ACTIVE jobs are eligible for matching embeddings
    if job.status != Job.Status.ACTIVE:
        return False, f"Job status is '{job.status}'; only '{Job.Status.ACTIVE}' jobs are eligible."

    # Expiry check
    if job.expires_at and job.expires_at <= timezone.now():
        return False, "Job has expired."

    # Non-empty title and description
    if not job.title or not job.title.strip():
        return False, "Job title is empty."

    if not job.description or not job.description.strip():
        return False, "Job description is empty."

    return True, None


def get_eligible_job_embeddings() -> models.QuerySet[JobEmbedding]:
    """
    Read-time filtering query helper.
    Returns a queryset of JobEmbedding records that are currently valid and eligible
    for vector similarity matching.
    Enforces:
    - Associated Job is active (status=Job.Status.ACTIVE)
    - Associated Job is not expired (expires_at is null or > now)
    - Associated Job has company and posted_by relationships
    - Embedding record is completed with non-null vector
    """
    now = timezone.now()
    return JobEmbedding.objects.filter(
        status=EmbeddingStatus.COMPLETED,
        embedding__isnull=False,
        job__status=Job.Status.ACTIVE,
        job__company__isnull=False,
        job__posted_by__isnull=False,
    ).filter(
        models.Q(job__expires_at__isnull=True) | models.Q(job__expires_at__gt=now)
    )


def invalidate_job_embedding(
    job_or_id: str | uuid.UUID | Job,
    reason: str = "Job is no longer eligible for matching.",
) -> bool:
    """
    Write-time invalidation helper.
    Invalidates any existing JobEmbedding for a job that has become ineligible, paused, or closed.
    Clears the embedding vector, advances generation version, and marks status FAILED.
    """
    job_id = job_or_id.id if isinstance(job_or_id, Job) else job_or_id
    updated_count = JobEmbedding.objects.filter(job_id=job_id).update(
        status=EmbeddingStatus.FAILED,
        error_message=reason,
        embedding=None,
        embedded_at=None,
        version=uuid.uuid4().hex[:16],
    )
    return updated_count > 0


@dataclass(frozen=True)
class PreparedJobText:
    """
    Structured container for prepared, normalized job text and metadata.
    """
    text: str
    content_hash: str
    character_count: int
    is_eligible: bool
    ineligibility_reason: str | None = None


class JobTextPreparationService:
    """
    Service for normalizing and structuring job description text for AI vector embeddings.
    Constructs deterministic text from stable, documented fields while excluding private/internal metadata.
    """

    @classmethod
    def prepare_text(cls, job: Job) -> PreparedJobText:
        """
        Builds a normalized, deterministic text representation of the job description
        suitable for generating a 2,048-dimensional passage embedding.

        Stable Documented Field Order:
        1. Job Title
        2. Company Name
        3. Role Type
        4. Experience Level
        5. Work Type
        6. Required Skills (deduplicated, sorted case-insensitively)
        7. Visa Requirements
        8. Job Description (normalized paragraph structure)

        Excluded Fields (Strictly private/internal):
        - salary_range (pay rate data)
        - jd_quality_score (internal admin rating)
        - jd_quality_feedback (internal reviewer feedback)
        - featured (promotional flag)
        - posted_by email or user details
        - database IDs, timestamps, URLs

        Character Bound Notice:
        The 16,000-character boundary enforced below is a conservative client-side character limit,
        NOT a guaranteed token limit. If text containing dense non-ASCII tokens exceeds the NVIDIA
        model's 4,096 token limit, the API response (HTTP 422) is caught as a permanent error.
        """
        is_eligible, reason = is_eligible_first_party_job(job)
        if not is_eligible:
            return PreparedJobText(
                text="",
                content_hash="",
                character_count=0,
                is_eligible=False,
                ineligibility_reason=reason,
            )

        sections: list[str] = []

        # 1. Title
        title = normalize_extracted_text(job.title or "")
        if title:
            sections.append(f"Job Title: {title}")

        # 2. Company Name
        company_name = ""
        if getattr(job, "company", None) and getattr(job.company, "name", None):
            company_name = normalize_extracted_text(job.company.name)
        if company_name:
            sections.append(f"Company: {company_name}")

        # 3. Role Type (Human readable)
        if job.role_type:
            role_label = dict(Job.RoleType.choices).get(job.role_type, job.role_type)
            sections.append(f"Role Type: {role_label}")

        # 4. Experience Level (Human readable)
        if job.experience_level:
            exp_label = dict(Job.ExperienceLevel.choices).get(job.experience_level, job.experience_level)
            sections.append(f"Experience Level: {exp_label}")

        # 5. Work Type
        if job.work_type:
            sections.append(f"Work Type: {job.work_type.capitalize()}")

        # 6. Tech Stack / Required Skills (Sorted deterministically)
        skills = cls._extract_normalized_skills(job.tech_stack)
        if skills:
            sections.append(f"Required Skills: {', '.join(skills)}")

        # 7. Visa Requirements
        if job.visa_requirements:
            visa_reqs = normalize_extracted_text(job.visa_requirements)
            if visa_reqs:
                sections.append(f"Visa Requirements: {visa_reqs}")

        # 8. Job Description (Normalized body text)
        description = normalize_extracted_text(job.description or "")
        if description:
            sections.append(f"\nJob Description:\n{description}")

        combined_text = "\n".join(sections).strip()

        # Enforce input character boundary (16,000 characters)
        if len(combined_text) > MAX_INPUT_CHARACTERS:
            combined_text = combined_text[:MAX_INPUT_CHARACTERS]

        content_hash = calculate_content_hash(combined_text)

        return PreparedJobText(
            text=combined_text,
            content_hash=content_hash,
            character_count=len(combined_text),
            is_eligible=True,
        )

    @staticmethod
    def _extract_normalized_skills(tech_stack: Any) -> list[str]:
        """
        Normalizes and deduplicates skills into an alphabetically sorted list.
        """
        if not tech_stack:
            return []

        raw_items: list[str] = []
        if isinstance(tech_stack, list):
            for item in tech_stack:
                if isinstance(item, str):
                    raw_items.extend(item.split(","))
                elif item:
                    raw_items.append(str(item))
        elif isinstance(tech_stack, str):
            raw_items.extend(tech_stack.split(","))

        cleaned_map: dict[str, str] = {}
        for item in raw_items:
            stripped = item.strip()
            if stripped:
                lower_key = stripped.lower()
                if lower_key not in cleaned_map:
                    cleaned_map[lower_key] = stripped

        return sorted(cleaned_map.values(), key=lambda s: s.lower())


@dataclass(frozen=True)
class JobEmbeddingResult:
    """
    Structured, sanitized result of job embedding generation.
    Never exposes raw text, embedding vectors, credentials, or internal paths.
    """
    job_id: str
    status: EmbeddingStatus
    content_hash: str | None = None
    dimensions: int | None = None
    model_name: str | None = None
    is_unchanged: bool = False
    is_stale: bool = False
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == EmbeddingStatus.COMPLETED


class JobEmbeddingService:
    """
    Service for generating dense 2,048-dimensional passage embeddings
    from eligible first-party employer job descriptions for AI vector matching.
    """

    def __init__(
        self,
        client: NvidiaEmbeddingClient | None = None,
        text_service: JobTextPreparationService | None = None,
    ) -> None:
        self.client = client or NvidiaEmbeddingClient()
        self.text_service = text_service or JobTextPreparationService()

    def generate_embedding_for_job(
        self,
        job_or_id: str | uuid.UUID | Job,
        force_regenerate: bool = False,
        raise_on_transient: bool = False,
    ) -> JobEmbeddingResult:
        """
        Generates and persists an embedding vector for an eligible first-party Job.

        :param job_or_id: Job instance or UUID.
        :param force_regenerate: If True, bypasses the unchanged content-hash check.
        :param raise_on_transient: If True, re-raises transient errors (for Celery retry).
        :return: JobEmbeddingResult with sanitized status and metadata.
        """
        # 1. Resolve Job instance
        if isinstance(job_or_id, Job):
            job = job_or_id
        else:
            try:
                job = Job.objects.select_related("company", "posted_by").get(id=job_or_id)
            except (Job.DoesNotExist, ValueError):
                return JobEmbeddingResult(
                    job_id=str(job_or_id),
                    status=EmbeddingStatus.FAILED,
                    error_message="Job does not exist.",
                )

        job_id_str = str(job.id)

        # 2. Check first-party eligibility and prepare normalized text
        prepared = self.text_service.prepare_text(job)
        if not prepared.is_eligible:
            err_msg = prepared.ineligibility_reason or "Job is not eligible for embedding generation."
            logger.info("Job %s is ineligible for embedding: %s", job_id_str, err_msg)

            # Invalidate any existing embedding record so ineligible jobs cannot be matched
            JobEmbedding.objects.filter(job=job).update(
                status=EmbeddingStatus.FAILED,
                error_message=err_msg,
                embedding=None,
                embedded_at=None,
                version=uuid.uuid4().hex[:16],
            )

            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                error_message=err_msg,
            )

        # 3. Retrieve or initialize JobEmbedding record
        job_embedding, _ = JobEmbedding.objects.get_or_create(job=job)

        current_hash = prepared.content_hash
        target_model = getattr(self.client, "model", TARGET_EMBEDDING_MODEL)

        # 4. Check for unchanged content (Idempotency)
        if not force_regenerate:
            if (
                job_embedding.status == EmbeddingStatus.COMPLETED
                and job_embedding.embedding is not None
                and job_embedding.content_hash == current_hash
                and job_embedding.model_name == target_model
                and job_embedding.dimensions == TARGET_EMBEDDING_DIMENSIONS
            ):
                logger.info(
                    "Job embedding up to date for job %s (hash=%s); skipping redundant call.",
                    job_id_str,
                    current_hash[:8],
                )
                return JobEmbeddingResult(
                    job_id=job_id_str,
                    status=EmbeddingStatus.COMPLETED,
                    content_hash=current_hash,
                    dimensions=job_embedding.dimensions,
                    model_name=job_embedding.model_name,
                    is_unchanged=True,
                )

        # Snapshot state before slow external API call (for concurrency & generation verification)
        snapshot_job_updated_at = job.updated_at
        snapshot_embedding_version = job_embedding.version
        snapshot_embedding_embedded_at = job_embedding.embedded_at
        snapshot_title = job.title
        snapshot_description = job.description
        snapshot_status = job.status
        snapshot_hash = current_hash
        snapshot_text = prepared.text

        # 5. Call NVIDIA Embedding Client (lock-free)
        try:
            embedding_result = self.client.embed(
                text=snapshot_text,
                input_type="passage",
            )
        except (EmbeddingTransientError, EmbeddingRateLimitError) as transient_err:
            logger.warning(
                "Transient error generating job embedding for job %s: %s",
                job_id_str,
                type(transient_err).__name__,
            )
            if raise_on_transient:
                raise
            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=f"Transient embedding error: {type(transient_err).__name__}",
            )
        except (
            EmbeddingValidationError,
            EmbeddingAuthenticationError,
            EmbeddingPermanentError,
            EmbeddingConfigurationError,
            EmbeddingDimensionError,
            EmbeddingResponseError,
            EmbeddingClientError,
        ) as perm_err:
            sanitized_msg = f"Embedding generation failed: {type(perm_err).__name__}"
            logger.error("Permanent error generating job embedding for %s: %s", job_id_str, sanitized_msg)

            # Protected error recording: do NOT overwrite a newer successful embedding
            with transaction.atomic():
                locked_job = Job.objects.select_for_update().filter(id=job.id).first()
                locked_record = JobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()

                if not locked_job or not locked_record:
                    return JobEmbeddingResult(job_id=job_id_str, status=EmbeddingStatus.FAILED, error_message=sanitized_msg)

                # If job or embedding was updated concurrently, discard this stale error
                if (
                    locked_job.updated_at != snapshot_job_updated_at
                    or locked_record.version != snapshot_embedding_version
                    or locked_record.embedded_at != snapshot_embedding_embedded_at
                    or locked_record.status == EmbeddingStatus.COMPLETED
                ):
                    logger.warning("Discarding stale error for job %s: job or embedding was updated concurrently.", job_id_str)
                    return JobEmbeddingResult(
                        job_id=job_id_str,
                        status=locked_record.status,
                        content_hash=locked_record.content_hash,
                        is_stale=True,
                        error_message=f"Stale error discarded: {sanitized_msg}",
                    )

                locked_record.status = EmbeddingStatus.FAILED
                locked_record.error_message = sanitized_msg
                locked_record.embedding = None
                locked_record.embedded_at = None
                locked_record.version = uuid.uuid4().hex[:16]
                locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])

            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=sanitized_msg,
            )
        except Exception as exc:
            sanitized_msg = f"Unexpected error during embedding generation: {type(exc).__name__}"
            logger.error("Unexpected error generating job embedding for %s: %s", job_id_str, sanitized_msg)

            # Protected error recording: do NOT overwrite a newer successful embedding
            with transaction.atomic():
                locked_job = Job.objects.select_for_update().filter(id=job.id).first()
                locked_record = JobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()

                if locked_job and locked_record:
                    if (
                        locked_job.updated_at != snapshot_job_updated_at
                        or locked_record.version != snapshot_embedding_version
                        or locked_record.embedded_at != snapshot_embedding_embedded_at
                        or locked_record.status == EmbeddingStatus.COMPLETED
                    ):
                        logger.warning("Discarding stale error for job %s: job or embedding was updated concurrently.", job_id_str)
                        return JobEmbeddingResult(
                            job_id=job_id_str,
                            status=locked_record.status,
                            content_hash=locked_record.content_hash,
                            is_stale=True,
                            error_message=f"Stale error discarded: {sanitized_msg}",
                        )

                    locked_record.status = EmbeddingStatus.FAILED
                    locked_record.error_message = sanitized_msg
                    locked_record.embedding = None
                    locked_record.embedded_at = None
                    locked_record.version = uuid.uuid4().hex[:16]
                    locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])

            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=sanitized_msg,
            )

        # 6. Validate vector dimensions and numeric finiteness
        vector = embedding_result.embedding
        if not isinstance(vector, list) or len(vector) != TARGET_EMBEDDING_DIMENSIONS:
            err_msg = (
                f"Invalid embedding dimensions: expected {TARGET_EMBEDDING_DIMENSIONS}, "
                f"received {len(vector) if isinstance(vector, list) else type(vector).__name__}."
            )
            logger.error("Dimension validation failed for job %s: %s", job_id_str, err_msg)
            with transaction.atomic():
                locked_record = JobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()
                if locked_record and locked_record.version == snapshot_embedding_version:
                    locked_record.status = EmbeddingStatus.FAILED
                    locked_record.error_message = err_msg
                    locked_record.embedding = None
                    locked_record.embedded_at = None
                    locked_record.version = uuid.uuid4().hex[:16]
                    locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
            err_msg = "Embedding vector contains invalid non-finite values (NaN, Inf)."
            logger.error("Finiteness validation failed for job %s: %s", job_id_str, err_msg)
            with transaction.atomic():
                locked_record = JobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()
                if locked_record and locked_record.version == snapshot_embedding_version:
                    locked_record.status = EmbeddingStatus.FAILED
                    locked_record.error_message = err_msg
                    locked_record.embedding = None
                    locked_record.embedded_at = None
                    locked_record.version = uuid.uuid4().hex[:16]
                    locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
            return JobEmbeddingResult(
                job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        # 7. Persist Vector with Concurrency, Generation & Stale Overwrite Protection
        with transaction.atomic():
            locked_job = (
                Job.objects.select_for_update()
                .filter(id=job.id)
                .first()
            )
            locked_record = (
                JobEmbedding.objects.select_for_update()
                .filter(id=job_embedding.id)
                .first()
            )

            if not locked_job or not locked_record:
                return JobEmbeddingResult(
                    job_id=job_id_str,
                    status=EmbeddingStatus.FAILED,
                    error_message="Job or JobEmbedding record disappeared during processing.",
                )

            # Re-check eligibility on locked record
            recheck_prepared = self.text_service.prepare_text(locked_job)
            if not recheck_prepared.is_eligible:
                logger.warning(
                    "Job %s became ineligible during external API call; discarding stale vector.",
                    job_id_str,
                )
                locked_record.status = EmbeddingStatus.FAILED
                locked_record.error_message = recheck_prepared.ineligibility_reason
                locked_record.embedding = None
                locked_record.embedded_at = None
                locked_record.version = uuid.uuid4().hex[:16]
                locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
                return JobEmbeddingResult(
                    job_id=job_id_str,
                    status=EmbeddingStatus.FAILED,
                    is_stale=True,
                    error_message="Stale embedding discarded because job became ineligible.",
                )

            # Re-check concurrency, generation, and content hash:
            # - Did the Job row change in any way (updated_at changed)? (handles ABA content edits)
            # - Did JobEmbedding change in any way (version or embedded_at changed)? (handles newer tasks finishing)
            # - Did the content hash, title, description, or status change?
            if (
                locked_job.updated_at != snapshot_job_updated_at
                or locked_record.version != snapshot_embedding_version
                or locked_record.embedded_at != snapshot_embedding_embedded_at
                or recheck_prepared.content_hash != snapshot_hash
                or locked_job.title != snapshot_title
                or locked_job.description != snapshot_description
                or locked_job.status != snapshot_status
            ):
                logger.warning(
                    "Job %s or its embedding generation was updated concurrently; discarding stale vector.",
                    job_id_str,
                )
                return JobEmbeddingResult(
                    job_id=job_id_str,
                    status=locked_record.status,
                    content_hash=locked_record.content_hash,
                    is_stale=True,
                    error_message="Stale embedding discarded because job content or generation was updated concurrently.",
                )

            # Safe to persist: all match
            new_generation_id = uuid.uuid4().hex[:16]
            locked_record.embedding = vector
            locked_record.model_name = embedding_result.model
            locked_record.dimensions = len(vector)
            locked_record.content_hash = snapshot_hash
            locked_record.text_length = len(snapshot_text)
            locked_record.version = new_generation_id
            locked_record.status = EmbeddingStatus.COMPLETED
            locked_record.error_message = None
            locked_record.embedded_at = timezone.now()
            locked_record.save(
                update_fields=[
                    "embedding",
                    "model_name",
                    "dimensions",
                    "content_hash",
                    "text_length",
                    "version",
                    "status",
                    "error_message",
                    "embedded_at",
                    "updated_at",
                ]
            )

        logger.info(
            "Successfully generated and persisted job embedding for job %s (dims=%d, model=%s, gen=%s)",
            job_id_str,
            len(vector),
            embedding_result.model,
            new_generation_id,
        )

        return JobEmbeddingResult(
            job_id=job_id_str,
            status=EmbeddingStatus.COMPLETED,
            content_hash=snapshot_hash,
            dimensions=len(vector),
            model_name=embedding_result.model,
        )
