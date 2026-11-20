"""
External Job Description Normalization and Embedding Generation Foundation
for PeopleRemotely AI Recommended External Jobs.

Features:
- Dedicated, testable service for preparing normalized external job text (ExternalJobTextPreparationService).
- Dedicated service for generating dense 2,048-dimensional passage embeddings for eligible external jobs (ExternalJobEmbeddingService).
- Strict external job eligibility enforcement:
  * is_active = True
  * status = ExternalJob.Status.ACTIVE
  * country = 'US'
  * remote_type IN (ExternalJob.RemoteType.REMOTE, ExternalJob.RemoteType.HYBRID)
  * Non-empty title and non-empty description.
- Deterministic text preparation from stable, documented fields (Title, Company, Remote Type, Tech Stack, Description).
- Bounded input text (up to 16,000 characters) client-side boundary matching NVIDIA Nemotron-3 1B model specs.
- Content-hash (SHA-256) idempotency to eliminate redundant NVIDIA API calls.
- Concurrency & stale overwrite protection using select_for_update(), generation identifier, and updated_at checks.
- Distinguishes retryable transient errors from non-retryable permanent errors.
- Strictly private: never logs or leaks raw vectors or credentials.
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
from external_jobs.models import ExternalJob
from external_jobs.utils import clean_html_text
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    EmbeddingStatus,
    ExternalJobEmbedding,
)

logger = logging.getLogger(__name__)


def is_eligible_external_job(job: Any) -> tuple[bool, str | None]:
    """
    Verifies if an external job satisfies all eligibility criteria for AI embedding generation:
    - Must be an instance of ExternalJob
    - is_active is True
    - status is ACTIVE
    - country is US
    - remote_type is REMOTE or HYBRID
    - Title is non-empty
    - Description is non-empty
    - Not expired (if expires_at is present)
    """
    if not isinstance(job, ExternalJob):
        return False, "Object is not an instance of ExternalJob model."

    if not job.is_active:
        return False, "ExternalJob is inactive (is_active=False)."

    if job.status != ExternalJob.Status.ACTIVE:
        return False, f"ExternalJob status is '{job.status}'; only '{ExternalJob.Status.ACTIVE}' jobs are eligible."

    if (job.country or "").strip().upper() != "US":
        return False, f"ExternalJob country is '{job.country}'; only 'US' jobs are eligible."

    eligible_remote_types = {
        ExternalJob.RemoteType.REMOTE,
        ExternalJob.RemoteType.HYBRID,
    }
    if job.remote_type not in eligible_remote_types:
        return False, f"ExternalJob remote_type is '{job.remote_type}'; must be REMOTE or HYBRID."

    # Expiration check
    if job.expires_at and job.expires_at <= timezone.now():
        return False, "ExternalJob has expired."

    # Non-empty title and description
    if not job.title or not job.title.strip():
        return False, "ExternalJob title is empty."

    cleaned_desc = clean_html_text(job.description or "")
    if not cleaned_desc or not cleaned_desc.strip():
        return False, "ExternalJob description is empty."

    return True, None


def get_eligible_external_job_embeddings() -> models.QuerySet[ExternalJobEmbedding]:
    """
    Read-time filtering query helper.
    Returns a queryset of ExternalJobEmbedding records that are currently valid
    and eligible for vector similarity recommendation matching.
    """
    now = timezone.now()
    return ExternalJobEmbedding.objects.filter(
        status=EmbeddingStatus.COMPLETED,
        embedding__isnull=False,
        external_job__is_active=True,
        external_job__status=ExternalJob.Status.ACTIVE,
        external_job__country="US",
        external_job__remote_type__in=[
            ExternalJob.RemoteType.REMOTE,
            ExternalJob.RemoteType.HYBRID,
        ],
    ).filter(
        models.Q(external_job__expires_at__isnull=True)
        | models.Q(external_job__expires_at__gt=now)
    )


@dataclass(frozen=True)
class PreparedExternalJobText:
    """Immutable value object holding normalized text prepared for passage embedding."""

    text: str
    content_hash: str
    character_count: int
    is_eligible: bool
    ineligibility_reason: str | None = None


class ExternalJobTextPreparationService:
    """
    Constructs deterministic, sanitized passage text from an ExternalJob record.
    Strips raw HTML, normalizes unicode/whitespace, and excludes volatile URLs and IDs.
    """

    @classmethod
    def prepare_text(cls, job: ExternalJob) -> PreparedExternalJobText:
        is_eligible, reason = is_eligible_external_job(job)
        if not is_eligible:
            return PreparedExternalJobText(
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
        company_name = normalize_extracted_text(job.company_name or "")
        if company_name:
            sections.append(f"Company: {company_name}")

        # 3. Remote Type & Location
        remote_label = dict(ExternalJob.RemoteType.choices).get(job.remote_type, job.remote_type)
        location_info = f"Remote Status: {remote_label}"
        if job.location:
            clean_loc = normalize_extracted_text(job.location)
            if clean_loc:
                location_info += f" ({clean_loc})"
        sections.append(location_info)

        # 4. Employment Type (if available)
        if job.employment_type:
            clean_emp = normalize_extracted_text(job.employment_type)
            if clean_emp:
                sections.append(f"Employment Type: {clean_emp}")

        # 5. Tech Stack / Skills (Deduplicated, canonical technical skills only)
        # Strips out generic category labels like "IT Jobs" and extracts real technical skills
        # from tech_stack and, if empty or generic, from title and description.
        skills = cls._extract_normalized_skills(job.tech_stack, fallback_text=f"{job.title}\n{job.description}")
        if skills:
            sections.append(f"Required Skills: {', '.join(skills)}")

        # 6. Normalized Description Body
        clean_desc = clean_html_text(job.description or "")
        desc = normalize_extracted_text(clean_desc)
        if desc:
            sections.append(f"\nJob Description:\n{desc}")

        combined_text = "\n".join(sections).strip()

        # Enforce input character boundary (16,000 characters)
        if len(combined_text) > MAX_INPUT_CHARACTERS:
            combined_text = combined_text[:MAX_INPUT_CHARACTERS]

        content_hash = calculate_content_hash(combined_text)

        return PreparedExternalJobText(
            text=combined_text,
            content_hash=content_hash,
            character_count=len(combined_text),
            is_eligible=True,
        )

    @classmethod
    def _extract_normalized_skills(
        cls, tech_stack: Any, fallback_text: str | None = None
    ) -> list[str]:
        from common.skill_extraction import extract_technical_skills

        # 1. Attempt extraction from tech_stack
        extracted = extract_technical_skills(tech_stack)
        if extracted:
            return extracted

        # 2. If tech_stack had only generic items or was empty, extract from title/description fallback
        if fallback_text:
            return extract_technical_skills(fallback_text)

        return []


@dataclass(frozen=True)
class ExternalJobEmbeddingResult:
    """Immutable result object returned by ExternalJobEmbeddingService."""

    external_job_id: str
    status: EmbeddingStatus
    content_hash: str = ""
    dimensions: int = 0
    model_name: str = TARGET_EMBEDDING_MODEL
    is_unchanged: bool = False
    is_stale: bool = False
    error_message: str | None = None


class ExternalJobEmbeddingService:
    """
    Generates and persists 2,048-dimensional passage embeddings for eligible ExternalJob records.
    Features content-hash idempotency, transaction-safe concurrency checks, and retryable exception propagation.
    """

    def __init__(
        self,
        client: NvidiaEmbeddingClient | None = None,
        text_service: type[ExternalJobTextPreparationService] = ExternalJobTextPreparationService,
    ) -> None:
        self.client = client or NvidiaEmbeddingClient()
        self.text_service = text_service

    def generate_embedding_for_job(
        self,
        job_or_id: str | uuid.UUID | ExternalJob,
        force_regenerate: bool = False,
        raise_on_transient: bool = False,
    ) -> ExternalJobEmbeddingResult:
        # 1. Fetch ExternalJob record
        if isinstance(job_or_id, ExternalJob):
            job = job_or_id
        else:
            try:
                job = ExternalJob.objects.select_related("source").get(id=job_or_id)
            except (ExternalJob.DoesNotExist, ValueError):
                job_id_str = str(job_or_id)
                logger.warning("ExternalJob %s not found; aborting embedding generation.", job_id_str)
                return ExternalJobEmbeddingResult(
                    external_job_id=job_id_str,
                    status=EmbeddingStatus.FAILED,
                    error_message=f"ExternalJob {job_id_str} does not exist.",
                )

        job_id_str = str(job.id)

        # 2. Check Eligibility & Prepare Input Text
        prepared = self.text_service.prepare_text(job)
        if not prepared.is_eligible:
            err_msg = f"ExternalJob ineligible: {prepared.ineligibility_reason}"
            logger.info("ExternalJob %s ineligible for embedding: %s", job_id_str, prepared.ineligibility_reason)

            ExternalJobEmbedding.objects.update_or_create(
                external_job=job,
                defaults={
                    "status": EmbeddingStatus.FAILED,
                    "error_message": err_msg,
                    "embedding": None,
                    "embedded_at": None,
                    "version": uuid.uuid4().hex[:16],
                },
            )

            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                error_message=err_msg,
            )

        # 3. Retrieve or initialize ExternalJobEmbedding record
        job_embedding, _ = ExternalJobEmbedding.objects.get_or_create(external_job=job)

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
                    "ExternalJob embedding up to date for job %s (hash=%s); skipping redundant call.",
                    job_id_str,
                    current_hash[:8],
                )
                return ExternalJobEmbeddingResult(
                    external_job_id=job_id_str,
                    status=EmbeddingStatus.COMPLETED,
                    content_hash=current_hash,
                    dimensions=job_embedding.dimensions,
                    model_name=job_embedding.model_name,
                    is_unchanged=True,
                )

        # Snapshot state before external API call (concurrency guard)
        snapshot_job_updated_at = job.updated_at
        snapshot_embedding_version = job_embedding.version
        snapshot_embedding_embedded_at = job_embedding.embedded_at
        snapshot_title = job.title
        snapshot_description = job.description
        snapshot_status = job.status
        snapshot_hash = current_hash
        snapshot_text = prepared.text

        # 5. Call NVIDIA Embedding Client
        try:
            embedding_result = self.client.embed(
                text=snapshot_text,
                input_type="passage",
            )
        except (EmbeddingTransientError, EmbeddingRateLimitError) as transient_err:
            logger.warning(
                "Transient error generating external job embedding for %s: %s",
                job_id_str,
                type(transient_err).__name__,
            )
            if raise_on_transient:
                raise
            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
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
            logger.error("Permanent error generating external job embedding for %s: %s", job_id_str, sanitized_msg)

            with transaction.atomic():
                locked_job = ExternalJob.objects.select_for_update().filter(id=job.id).first()
                locked_record = ExternalJobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()

                if not locked_job or not locked_record:
                    return ExternalJobEmbeddingResult(
                        external_job_id=job_id_str,
                        status=EmbeddingStatus.FAILED,
                        error_message=sanitized_msg,
                    )

                if (
                    locked_job.updated_at != snapshot_job_updated_at
                    or locked_record.version != snapshot_embedding_version
                    or locked_record.embedded_at != snapshot_embedding_embedded_at
                    or locked_record.status == EmbeddingStatus.COMPLETED
                ):
                    logger.warning("Discarding stale error for external job %s: updated concurrently.", job_id_str)
                    return ExternalJobEmbeddingResult(
                        external_job_id=job_id_str,
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

            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=sanitized_msg,
            )
        except Exception as exc:
            sanitized_msg = f"Unexpected error during external embedding generation: {type(exc).__name__}"
            logger.error("Unexpected error generating external job embedding for %s: %s", job_id_str, sanitized_msg)

            with transaction.atomic():
                locked_job = ExternalJob.objects.select_for_update().filter(id=job.id).first()
                locked_record = ExternalJobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()

                if locked_job and locked_record:
                    if (
                        locked_job.updated_at != snapshot_job_updated_at
                        or locked_record.version != snapshot_embedding_version
                        or locked_record.embedded_at != snapshot_embedding_embedded_at
                        or locked_record.status == EmbeddingStatus.COMPLETED
                    ):
                        logger.warning("Discarding stale error for external job %s: updated concurrently.", job_id_str)
                        return ExternalJobEmbeddingResult(
                            external_job_id=job_id_str,
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

            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
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
            logger.error("Dimension validation failed for external job %s: %s", job_id_str, err_msg)
            with transaction.atomic():
                locked_record = ExternalJobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()
                if locked_record and locked_record.version == snapshot_embedding_version:
                    locked_record.status = EmbeddingStatus.FAILED
                    locked_record.error_message = err_msg
                    locked_record.embedding = None
                    locked_record.embedded_at = None
                    locked_record.version = uuid.uuid4().hex[:16]
                    locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
            err_msg = "Embedding vector contains invalid non-finite values (NaN, Inf)."
            logger.error("Finiteness validation failed for external job %s: %s", job_id_str, err_msg)
            with transaction.atomic():
                locked_record = ExternalJobEmbedding.objects.select_for_update().filter(id=job_embedding.id).first()
                if locked_record and locked_record.version == snapshot_embedding_version:
                    locked_record.status = EmbeddingStatus.FAILED
                    locked_record.error_message = err_msg
                    locked_record.embedding = None
                    locked_record.embedded_at = None
                    locked_record.version = uuid.uuid4().hex[:16]
                    locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
            return ExternalJobEmbeddingResult(
                external_job_id=job_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        # 7. Persist Vector with Concurrency & Stale Overwrite Protection
        with transaction.atomic():
            locked_job = (
                ExternalJob.objects.select_for_update()
                .filter(id=job.id)
                .first()
            )
            locked_record = (
                ExternalJobEmbedding.objects.select_for_update()
                .filter(id=job_embedding.id)
                .first()
            )

            if not locked_job or not locked_record:
                return ExternalJobEmbeddingResult(
                    external_job_id=job_id_str,
                    status=EmbeddingStatus.FAILED,
                    error_message="ExternalJob or ExternalJobEmbedding record disappeared during processing.",
                )

            # Re-check eligibility on locked record
            recheck_prepared = self.text_service.prepare_text(locked_job)
            if not recheck_prepared.is_eligible:
                logger.warning(
                    "ExternalJob %s became ineligible during external API call; discarding stale vector.",
                    job_id_str,
                )
                locked_record.status = EmbeddingStatus.FAILED
                locked_record.error_message = recheck_prepared.ineligibility_reason
                locked_record.embedding = None
                locked_record.embedded_at = None
                locked_record.version = uuid.uuid4().hex[:16]
                locked_record.save(update_fields=["status", "error_message", "embedding", "embedded_at", "version", "updated_at"])
                return ExternalJobEmbeddingResult(
                    external_job_id=job_id_str,
                    status=EmbeddingStatus.FAILED,
                    is_stale=True,
                    error_message="Stale embedding discarded because external job became ineligible.",
                )

            # Concurrency validation
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
                    "ExternalJob %s or its embedding was updated concurrently; discarding stale vector.",
                    job_id_str,
                )
                return ExternalJobEmbeddingResult(
                    external_job_id=job_id_str,
                    status=locked_record.status,
                    content_hash=locked_record.content_hash,
                    is_stale=True,
                    error_message="Stale embedding discarded because external job content or generation was updated concurrently.",
                )

            # Safe to persist
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
            "Successfully generated and persisted embedding for external job %s (dims=%d, model=%s, gen=%s)",
            job_id_str,
            len(vector),
            embedding_result.model,
            new_generation_id,
        )

        return ExternalJobEmbeddingResult(
            external_job_id=job_id_str,
            status=EmbeddingStatus.COMPLETED,
            content_hash=snapshot_hash,
            dimensions=len(vector),
            model_name=embedding_result.model,
            is_unchanged=False,
        )
