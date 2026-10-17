"""
Resume Embedding Generation Foundation for PeopleRemotely AI Matching.

Features:
- Dedicated, testable service for generating candidate resume embeddings.
- Reads normalized extracted resume text from private backend-only storage (CandidateResumeEmbedding).
- Rejects missing, empty, whitespace-only, failed, or corrupt extraction results.
- Enforces content-hash idempotency to prevent redundant API calls for unchanged resumes.
- Calls NvidiaEmbeddingClient with input_type="passage" using configured model & endpoint.
- Validates that returned vectors contain exactly 2,048 finite numeric values.
- Persists vector and metadata (model_name, dimensions, content_hash, text_length, embedded_at).
- Concurrency & stale overwrite protection using select_for_update() and content_hash re-check.
- Distinguishes retryable transient errors from non-retryable permanent errors.
- Strictly private: never logs or leaks resume text, vectors, credentials, or internal paths.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Any, Final

from django.db import transaction
from django.utils import timezone

from candidates.models import CandidateProfile
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
from common.resume_extraction import calculate_content_hash, calculate_source_fingerprint
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    CandidateResumeEmbedding,
    EmbeddingStatus,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResumeEmbeddingResult:
    """
    Structured, sanitized result of resume embedding generation.
    Never exposes raw text, embedding vectors, credentials, or internal storage paths.
    """

    candidate_profile_id: str
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


class ResumeEmbeddingService:
    """
    Service for generating dense 2,048-dimensional passage embeddings
    from candidate resumes for AI vector matching.
    """

    def __init__(
        self,
        client: NvidiaEmbeddingClient | None = None,
    ) -> None:
        self.client = client or NvidiaEmbeddingClient()

    def generate_embedding_for_candidate(
        self,
        candidate_profile_or_id: str | uuid.UUID | CandidateProfile,
        force_regenerate: bool = False,
        raise_on_transient: bool = False,
    ) -> ResumeEmbeddingResult:
        """
        Generates and persists an embedding vector for a candidate's extracted resume text.

        :param candidate_profile_or_id: CandidateProfile model instance or UUID.
        :param force_regenerate: If True, bypasses the unchanged content-hash check.
        :param raise_on_transient: If True, re-raises transient errors (e.g. for Celery retry).
        :return: ResumeEmbeddingResult with sanitized status and metadata.
        """
        # 1. Resolve CandidateProfile
        if isinstance(candidate_profile_or_id, CandidateProfile):
            candidate_profile = candidate_profile_or_id
        else:
            try:
                candidate_profile = CandidateProfile.objects.select_related("user").get(
                    id=candidate_profile_or_id
                )
            except (CandidateProfile.DoesNotExist, ValueError):
                return ResumeEmbeddingResult(
                    candidate_profile_id=str(candidate_profile_or_id),
                    status=EmbeddingStatus.FAILED,
                    error_message="Candidate profile does not exist.",
                )

        profile_id_str = str(candidate_profile.id)

        # 2. Retrieve CandidateResumeEmbedding record
        try:
            resume_embedding = CandidateResumeEmbedding.objects.get(
                candidate_profile=candidate_profile
            )
        except CandidateResumeEmbedding.DoesNotExist:
            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                error_message="No resume embedding record found. Resume text must be extracted first.",
            )

        # 3. Validate resume source synchronization & extracted text
        expected_fingerprint = calculate_source_fingerprint(candidate_profile.resume_url)
        if (
            expected_fingerprint
            and resume_embedding.version
            and resume_embedding.version not in ("", "v1", expected_fingerprint)
        ):
            err_msg = "Resume text is out of sync with current resume file. Extraction must be re-run."
            logger.warning(
                "Resume for candidate %s is out of sync (expected %s, got %s)",
                profile_id_str,
                expected_fingerprint[:8],
                resume_embedding.version[:8],
            )
            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                is_stale=True,
                error_message=err_msg,
            )

        extracted_text = resume_embedding.extracted_text
        if not extracted_text or not extracted_text.strip():
            err_msg = (
                "Resume extraction failed previously."
                if resume_embedding.status == EmbeddingStatus.FAILED
                else "No extracted resume text available for embedding generation."
            )
            if resume_embedding.status != EmbeddingStatus.FAILED:
                resume_embedding.status = EmbeddingStatus.FAILED
                resume_embedding.error_message = err_msg
                resume_embedding.save(update_fields=["status", "error_message", "updated_at"])

            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                error_message=err_msg,
            )

        # Check content hash
        current_hash = resume_embedding.content_hash or calculate_content_hash(extracted_text)

        # 4. Check for unchanged content (Idempotency)
        target_model = getattr(self.client, "model", TARGET_EMBEDDING_MODEL)
        if not force_regenerate:
            if (
                resume_embedding.status == EmbeddingStatus.COMPLETED
                and resume_embedding.embedding is not None
                and resume_embedding.content_hash == current_hash
                and resume_embedding.model_name == target_model
                and resume_embedding.dimensions == TARGET_EMBEDDING_DIMENSIONS
            ):
                logger.info(
                    "Resume embedding up to date for candidate %s (hash=%s); skipping redundant call.",
                    profile_id_str,
                    current_hash[:8],
                )
                return ResumeEmbeddingResult(
                    candidate_profile_id=profile_id_str,
                    status=EmbeddingStatus.COMPLETED,
                    content_hash=current_hash,
                    dimensions=resume_embedding.dimensions,
                    model_name=resume_embedding.model_name,
                    is_unchanged=True,
                )

        # Snapshot state before slow external API call
        snapshot_resume_url = candidate_profile.resume_url
        snapshot_version = resume_embedding.version
        snapshot_content_hash = current_hash
        snapshot_text = extracted_text

        # 5. Prepare text bounded by client sequence limits (16,000 chars)
        text_to_embed = extracted_text[:MAX_INPUT_CHARACTERS]

        # 6. Call NVIDIA Embedding Client
        try:
            embedding_result = self.client.embed(
                text=text_to_embed,
                input_type="passage",
            )
        except (EmbeddingTransientError, EmbeddingRateLimitError) as transient_err:
            logger.warning(
                "Transient error generating resume embedding for candidate %s: %s",
                profile_id_str,
                type(transient_err).__name__,
            )
            if raise_on_transient:
                raise
            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
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
            logger.error(
                "Permanent error generating resume embedding for candidate %s: %s",
                profile_id_str,
                sanitized_msg,
            )
            resume_embedding.status = EmbeddingStatus.FAILED
            resume_embedding.error_message = sanitized_msg
            resume_embedding.save(update_fields=["status", "error_message", "updated_at"])

            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=sanitized_msg,
            )
        except Exception as exc:
            sanitized_msg = f"Unexpected error during embedding generation: {type(exc).__name__}"
            logger.error(
                "Unexpected error generating resume embedding for candidate %s: %s",
                profile_id_str,
                sanitized_msg,
            )
            resume_embedding.status = EmbeddingStatus.FAILED
            resume_embedding.error_message = sanitized_msg
            resume_embedding.save(update_fields=["status", "error_message", "updated_at"])

            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=sanitized_msg,
            )

        # 7. Validate vector dimensions and numeric finiteness
        vector = embedding_result.embedding
        if not isinstance(vector, list) or len(vector) != TARGET_EMBEDDING_DIMENSIONS:
            err_msg = (
                f"Invalid embedding dimensions: expected {TARGET_EMBEDDING_DIMENSIONS}, "
                f"received {len(vector) if isinstance(vector, list) else type(vector).__name__}."
            )
            logger.error("Dimension validation failed for candidate %s: %s", profile_id_str, err_msg)
            resume_embedding.status = EmbeddingStatus.FAILED
            resume_embedding.error_message = err_msg
            resume_embedding.save(update_fields=["status", "error_message", "updated_at"])
            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
            err_msg = "Embedding vector contains invalid non-finite values (NaN, Inf)."
            logger.error("Finiteness validation failed for candidate %s: %s", profile_id_str, err_msg)
            resume_embedding.status = EmbeddingStatus.FAILED
            resume_embedding.error_message = err_msg
            resume_embedding.save(update_fields=["status", "error_message", "updated_at"])
            return ResumeEmbeddingResult(
                candidate_profile_id=profile_id_str,
                status=EmbeddingStatus.FAILED,
                content_hash=current_hash,
                error_message=err_msg,
            )

        # 8. Persist Vector with Concurrency & Stale Overwrite Protection
        with transaction.atomic():
            locked_record = (
                CandidateResumeEmbedding.objects.select_for_update()
                .filter(id=resume_embedding.id)
                .first()
            )
            locked_profile = (
                CandidateProfile.objects.select_for_update()
                .filter(id=candidate_profile.id)
                .first()
            )

            if not locked_record or not locked_profile:
                return ResumeEmbeddingResult(
                    candidate_profile_id=profile_id_str,
                    status=EmbeddingStatus.FAILED,
                    error_message="Resume embedding or candidate profile record disappeared during processing.",
                )

            # Re-check content hash, text, version, and resume_url to avoid overwriting a newer resume
            if (
                locked_record.content_hash != snapshot_content_hash
                or locked_record.extracted_text != snapshot_text
                or locked_record.version != snapshot_version
                or locked_profile.resume_url != snapshot_resume_url
            ):
                logger.warning(
                    "Resume text or file for candidate %s was updated concurrently; discarding stale vector.",
                    profile_id_str,
                )
                return ResumeEmbeddingResult(
                    candidate_profile_id=profile_id_str,
                    status=locked_record.status,
                    content_hash=locked_record.content_hash,
                    is_stale=True,
                    error_message="Stale embedding discarded because resume was updated concurrently.",
                )

            # Safe to persist: all match
            locked_record.embedding = vector
            locked_record.model_name = embedding_result.model
            locked_record.dimensions = len(vector)
            locked_record.content_hash = snapshot_content_hash
            locked_record.text_length = len(snapshot_text)
            locked_record.version = snapshot_version
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
            "Successfully generated and persisted resume embedding for candidate %s (dims=%d, model=%s)",
            profile_id_str,
            len(vector),
            embedding_result.model,
        )

        return ResumeEmbeddingResult(
            candidate_profile_id=profile_id_str,
            status=EmbeddingStatus.COMPLETED,
            content_hash=current_hash,
            dimensions=len(vector),
            model_name=embedding_result.model,
        )
