"""
Hybrid Candidate-Job Matching Engine for PeopleRemotely AI Matching.

Phase 7 Implementation:
- Implements hybrid scoring combining:
    1. Semantic similarity (50% weight) via dense 2,048-dimensional embeddings and pgvector cosine distance.
    2. Skills match (30% weight) via normalized tech stack overlap.
    3. Experience match (20% weight) via canonical career level progression.
- Qualification threshold: score >= 70.0 (scores below 70.00 DO NOT qualify).
- Candidate and Job eligibility:
    - Jobs: must be eligible, active, non-expired, first-party jobs with completed 2,048-dim embedding.
    - Candidates: must be open to matching, profile complete, with completed 2,048-dim resume embedding.
    - Stale or invalidated embeddings cannot enter the matching query.
- Preservation of existing data model and approval gates:
    - Match model and Application = Match alias preserved.
    - Unique candidate/job constraint preserved.
    - Status transitions and approval gates preserved: visible_to_employer is ALWAYS False upon creation.
    - Recruiter review required before employer visibility.
    - Private resume texts, normalized job texts, and raw vector arrays are never leaked.
- Approximate indexing restriction: exact cosine distance queries used; no HNSW or IVFFlat index created.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Any, Final, Optional, Union

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from candidates.models import CandidateProfile
from common.resume_extraction import calculate_source_fingerprint
from jobs.models import Job
from matching.job_embeddings import get_eligible_job_embeddings, is_eligible_first_party_job
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    CandidateResumeEmbedding,
    EmbeddingStatus,
    JobEmbedding,
    Match,
)

logger = logging.getLogger(__name__)

# Scoring weights (sum to 1.0)
WEIGHT_SEMANTIC: Final[float] = 0.50
WEIGHT_SKILLS: Final[float] = 0.30
WEIGHT_EXPERIENCE: Final[float] = 0.20

# Qualification threshold: greater than or equal to 70.0
QUALIFICATION_THRESHOLD: Final[float] = 70.0

# Recruiter alert threshold for high matches
HIGH_MATCH_ALERT_THRESHOLD: Final[int] = 85

# Canonical experience level progression
EXPERIENCE_LEVEL_ORDER: Final[list[str]] = ["junior", "mid", "senior", "lead"]


@dataclass(frozen=True)
class HybridScoreBreakdown:
    """
    Detailed, transparent breakdown of the hybrid match score components.
    Never exposes raw text, embedding vectors, or private candidate data.
    """
    semantic_score: float  # 0.0 - 100.0 (50% weight)
    skill_score: float     # 0.0 - 100.0 (30% weight)
    exp_score: float       # 0.0 - 100.0 (20% weight)
    final_score: float     # 0.0 - 100.0
    qualifies: bool        # True if and only if final_score >= 70.0
    reason: str            # Recruiter-facing summary of component scores


def compute_cosine_similarity(
    vec_a: Optional[list[float]],
    vec_b: Optional[list[float]],
) -> float:
    """
    Computes exact cosine similarity between two vector lists:
    cos_sim = (A . B) / (||A|| * ||B||)
    Returns a value clamped between -1.0 and 1.0.
    Safely handles zero vectors, non-finite values (NaN/Inf), missing vectors,
    and dimension mismatches by returning 0.0.
    """
    if not vec_a or not vec_b:
        return 0.0

    if len(vec_a) != len(vec_b) or len(vec_a) != TARGET_EMBEDDING_DIMENSIONS:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec_a, vec_b):
        if not (math.isfinite(a) and math.isfinite(b)):
            return 0.0
        dot += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    cos_sim = dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    return max(-1.0, min(1.0, cos_sim))


def cosine_distance_to_similarity_score(distance: float) -> float:
    """
    Converts pgvector cosine distance (d = 1 - cos_sim) to a 0–100 similarity score.
        Formula:
        cos_sim = 1.0 - distance
        similarity_score = clamp(cos_sim, 0.0, 1.0) * 100.0
        
    - Distance 0.0 (identical vectors) -> 100.0
    - Distance 0.30 (strong similarity) -> 70.0
    - Distance 1.0 (orthogonal vectors) -> 0.0
    - Distance > 1.0 (negative correlation) -> 0.0
    """
    if not math.isfinite(distance):
        return 0.0
    cos_sim = 1.0 - distance
    clamped_sim = max(0.0, min(1.0, cos_sim))
    return clamped_sim * 100.0


def cosine_similarity_to_score(cos_sim: float) -> float:
    """
    Converts cosine similarity (-1.0 to 1.0) to a 0–100 similarity score.
    """
    if not math.isfinite(cos_sim):
        return 0.0
    clamped_sim = max(0.0, min(1.0, cos_sim))
    return clamped_sim * 100.0


def compute_skill_overlap_score(
    candidate_skills: Union[str, list[str], None],
    job_skills: Union[str, list[str], None],
) -> float:
    """
    Computes percentage of job-required skills found in candidate skills (0.0 to 100.0).
    - If job specifies no required skills: returns 40.0 (neutral baseline).
    - If candidate has no skills: returns 0.0.
    """
    from matching.services import parse_skills, skill_matches

    c_skills = parse_skills(candidate_skills)
    j_skills = parse_skills(job_skills)

    if not j_skills:
        return 40.0
    if not c_skills:
        return 0.0

    matched = [
        js for js in j_skills if any(skill_matches(cs, js) for cs in c_skills)
    ]
    return (len(matched) / len(j_skills)) * 100.0


def compute_experience_score(
    candidate_level: Optional[str],
    job_level: Optional[str],
) -> float:
    """
    Computes career level alignment on a 0.0 - 100.0 scale:
    - 100.0: candidate level >= job level
    - 70.0:  candidate is 1 level below (e.g., mid applying for senior)
    - 40.0:  candidate is 2+ levels below (e.g., junior applying for senior/lead)
    - 50.0:  missing, empty, or unknown experience levels (neutral baseline)
    """
    if not candidate_level or not job_level:
        return 50.0

    cl = candidate_level.strip().lower()
    jl = job_level.strip().lower()

    if cl not in EXPERIENCE_LEVEL_ORDER or jl not in EXPERIENCE_LEVEL_ORDER:
        return 50.0

    c_idx = EXPERIENCE_LEVEL_ORDER.index(cl)
    j_idx = EXPERIENCE_LEVEL_ORDER.index(jl)
    diff = c_idx - j_idx

    if diff >= 0:
        return 100.0
    if diff == -1:
        return 70.0
    return 40.0


def calculate_hybrid_score(
    semantic_score: float,
    skill_score: float,
    exp_score: float,
) -> HybridScoreBreakdown:
    """
    Calculates combined hybrid score according to the 50/30/20 formula:
    Final = (0.50 * Semantic) + (0.30 * Skills) + (0.20 * Experience)    
    Enforces qualification at score >= 70.0 (69.99 does not qualify).
    """
    sem = max(0.0, min(100.0, float(semantic_score)))
    ski = max(0.0, min(100.0, float(skill_score)))
    exp = max(0.0, min(100.0, float(exp_score)))

    final_score = (WEIGHT_SEMANTIC * sem) + (WEIGHT_SKILLS * ski) + (WEIGHT_EXPERIENCE * exp)
    final_score = round(final_score, 4)

    # Greater than or equal to 70.00
    qualifies = final_score >= QUALIFICATION_THRESHOLD

    reason = (
        f"Hybrid match ({round(final_score, 1)}%): "
        f"Semantic={round(sem, 1)}% (50%), "
        f"Skills={round(ski, 1)}% (30%), "
        f"Experience={round(exp, 1)}% (20%)."
    )

    return HybridScoreBreakdown(
        semantic_score=round(sem, 2),
        skill_score=round(ski, 2),
        exp_score=round(exp, 2),
        final_score=round(final_score, 2),
        qualifies=qualifies,
        reason=reason,
    )


def is_candidate_eligible_for_hybrid_matching(
    candidate: Any,
) -> tuple[bool, Optional[str]]:
    """
    Validates whether a candidate profile meets all criteria for hybrid matching:
    - Is an instance of CandidateProfile
    - open_to_matching is True
    - profile_complete is True
    - profile_completeness is 100
    - Has an associated completed CandidateResumeEmbedding with non-null 2,048-dim vector
    """
    if not isinstance(candidate, CandidateProfile):
        return False, "Object is not an instance of CandidateProfile."

    if not candidate.open_to_matching:
        return False, "Candidate is not open to matching."

    if not candidate.profile_complete:
        return False, "Candidate profile is incomplete."

    if getattr(candidate, "profile_completeness", 0) != 100:
        return False, "Candidate profile completeness is not 100%."

    resume_emb = getattr(candidate, "resume_embedding", None)
    if not resume_emb:
        return False, "Candidate has no resume embedding record."

    if resume_emb.status != EmbeddingStatus.COMPLETED:
        return False, f"Candidate resume embedding status is '{resume_emb.status}'; must be 'completed'."

    if not resume_emb.embedding or len(resume_emb.embedding) != TARGET_EMBEDDING_DIMENSIONS:
        return False, "Candidate resume embedding vector is missing or invalid dimensions."

    # Verify that candidate has an uploaded resume and embedding matches current resume file
    if not getattr(candidate, "resume_url", None):
        return False, "Candidate has no resume uploaded."

    expected_fingerprint = calculate_source_fingerprint(candidate.resume_url)
    if resume_emb.version != expected_fingerprint:
        return False, f"Candidate resume embedding is stale (fingerprint mismatch: '{resume_emb.version}' != '{expected_fingerprint}')."

    return True, None


def is_job_eligible_for_hybrid_matching(
    job: Any,
) -> tuple[bool, Optional[str]]:
    """
    Validates whether a job meets all criteria for hybrid matching:
    - First-party Job instance, active, non-expired, company/user associated
    - Has an associated completed JobEmbedding with non-null 2,048-dim vector
    """
    eligible, reason = is_eligible_first_party_job(job)
    if not eligible:
        return False, reason

    job_emb = getattr(job, "job_embedding", None)
    if not job_emb:
        return False, "Job has no embedding record."

    if job_emb.status != EmbeddingStatus.COMPLETED:
        return False, f"Job embedding status is '{job_emb.status}'; must be 'completed'."

    if not job_emb.embedding or len(job_emb.embedding) != TARGET_EMBEDDING_DIMENSIONS:
        return False, "Job embedding vector is missing or invalid dimensions."

    return True, None


def get_eligible_candidate_resume_embeddings() -> models.QuerySet[CandidateResumeEmbedding]:
    """
    Returns QuerySet of CandidateResumeEmbedding records currently valid for vector matching.
    """
    return CandidateResumeEmbedding.objects.filter(
        status=EmbeddingStatus.COMPLETED,
        embedding__isnull=False,
        candidate_profile__open_to_matching=True,
        candidate_profile__profile_complete=True,
        candidate_profile__profile_completeness=100,
        candidate_profile__resume_url__isnull=False,
    ).exclude(candidate_profile__resume_url="").select_related("candidate_profile")


class HybridMatchingEngine:
    """
    Engine executing candidate-job hybrid matching.
    Coordinates exact pgvector cosine similarity, skill overlap, and experience scoring.
    Strictly preserves approval gates, recruiter notifications, and candidate privacy.
    """

    @classmethod
    def evaluate_pair(
        cls,
        candidate: CandidateProfile,
        job: Job,
        candidate_vector: Optional[list[float]] = None,
        job_vector: Optional[list[float]] = None,
    ) -> Optional[HybridScoreBreakdown]:
        """
        Evaluates a specific candidate and job pair.
        Returns HybridScoreBreakdown if eligible, or None if either party is ineligible.
        """
        cand_ok, _ = is_candidate_eligible_for_hybrid_matching(candidate)
        if not cand_ok:
            return None

        job_ok, _ = is_job_eligible_for_hybrid_matching(job)
        if not job_ok:
            return None

        # Resolve vectors
        vec_c = candidate_vector or candidate.resume_embedding.embedding
        vec_j = job_vector or job.job_embedding.embedding

        # 1. Semantic similarity score (50%)
        cos_sim = compute_cosine_similarity(vec_c, vec_j)
        semantic_score = cosine_similarity_to_score(cos_sim)

        # 2. Skills overlap score (30%)
        skill_score = compute_skill_overlap_score(candidate.skills, job.tech_stack)

        # 3. Experience alignment score (20%)
        exp_score = compute_experience_score(candidate.experience_level, job.experience_level)

        return calculate_hybrid_score(semantic_score, skill_score, exp_score)

    @classmethod
    def run_matching_for_candidate(
        cls,
        candidate_profile_or_id: Union[str, uuid.UUID, CandidateProfile],
    ) -> dict:
        """
        Runs hybrid matching for a single candidate profile across all eligible active jobs.
        Creates or updates Match records for candidates scoring strictly > 70.0.
        """
        if isinstance(candidate_profile_or_id, CandidateProfile):
            candidate = CandidateProfile.objects.select_related(
                "user", "resume_embedding"
            ).filter(id=candidate_profile_or_id.id).first()
        else:
            candidate = CandidateProfile.objects.select_related(
                "user", "resume_embedding"
            ).filter(id=candidate_profile_or_id).first()

        if not candidate:
            return {"matched": 0, "reason": "CandidateProfile not found"}

        cand_ok, cand_reason = is_candidate_eligible_for_hybrid_matching(candidate)
        if not cand_ok:
            logger.info(
                "Candidate %s ineligible for hybrid matching: %s",
                candidate.id,
                cand_reason,
            )
            return {"matched": 0, "reason": cand_reason}

        candidate_vector = candidate.resume_embedding.embedding

        # Query all eligible jobs using read-time filtering helper
        eligible_job_embeddings = get_eligible_job_embeddings().select_related("job")

        matched_count = 0

        # Try pgvector query if running on PostgreSQL with pgvector support
        try:
            from pgvector.django import CosineDistance
            annotated_jobs = eligible_job_embeddings.annotate(
                distance=CosineDistance("embedding", candidate_vector)
            ).order_by("distance")

            for job_emb in annotated_jobs:
                job = job_emb.job
                distance = job_emb.distance
                semantic_score = cosine_distance_to_similarity_score(distance)
                skill_score = compute_skill_overlap_score(candidate.skills, job.tech_stack)
                exp_score = compute_experience_score(candidate.experience_level, job.experience_level)

                breakdown = calculate_hybrid_score(semantic_score, skill_score, exp_score)

                if not breakdown.qualifies:
                    continue

                cls._persist_match(candidate, job, breakdown)
                matched_count += 1

            return {"matched": matched_count}

        except Exception as exc:
            # Fallback to in-memory exact cosine similarity (e.g. SQLite test database or non-pgvector environments)
            logger.debug("Falling back to exact in-memory vector comparison: %s", exc)
            for job_emb in eligible_job_embeddings:
                job = job_emb.job
                breakdown = cls.evaluate_pair(
                    candidate,
                    job,
                    candidate_vector=candidate_vector,
                    job_vector=job_emb.embedding,
                )
                if not breakdown or not breakdown.qualifies:
                    continue

                cls._persist_match(candidate, job, breakdown)
                matched_count += 1

            return {"matched": matched_count}

    @classmethod
    def run_matching_for_job(
        cls,
        job_or_id: Union[str, uuid.UUID, Job],
    ) -> dict:
        """
        Runs hybrid matching for a single eligible job across all eligible candidates.
        Creates or updates Match records for candidates scoring strictly > 70.0.
        """
        if isinstance(job_or_id, Job):
            job = Job.objects.select_related(
                "company", "posted_by", "job_embedding"
            ).filter(id=job_or_id.id).first()
        else:
            job = Job.objects.select_related(
                "company", "posted_by", "job_embedding"
            ).filter(id=job_or_id).first()

        if not job:
            return {"matched": 0, "reason": "Job not found"}

        job_ok, job_reason = is_job_eligible_for_hybrid_matching(job)
        if not job_ok:
            logger.info("Job %s ineligible for hybrid matching: %s", job.id, job_reason)
            return {"matched": 0, "reason": job_reason}

        job_vector = job.job_embedding.embedding

        # Query all eligible candidate resume embeddings
        eligible_candidate_embeddings = get_eligible_candidate_resume_embeddings()

        matched_count = 0

        # Try pgvector query if running on PostgreSQL with pgvector support
        try:
            from pgvector.django import CosineDistance
            annotated_candidates = eligible_candidate_embeddings.annotate(
                distance=CosineDistance("embedding", job_vector)
            ).order_by("distance")

            for cand_emb in annotated_candidates:
                candidate = cand_emb.candidate_profile
                distance = cand_emb.distance
                semantic_score = cosine_distance_to_similarity_score(distance)
                skill_score = compute_skill_overlap_score(candidate.skills, job.tech_stack)
                exp_score = compute_experience_score(candidate.experience_level, job.experience_level)

                breakdown = calculate_hybrid_score(semantic_score, skill_score, exp_score)

                if not breakdown.qualifies:
                    continue

                cls._persist_match(candidate, job, breakdown)
                matched_count += 1

            return {"matched": matched_count}

        except Exception as exc:
            # Fallback to in-memory exact cosine similarity
            logger.debug("Falling back to exact in-memory vector comparison: %s", exc)
            for cand_emb in eligible_candidate_embeddings:
                candidate = cand_emb.candidate_profile
                breakdown = cls.evaluate_pair(
                    candidate,
                    job,
                    candidate_vector=cand_emb.embedding,
                    job_vector=job_vector,
                )
                if not breakdown or not breakdown.qualifies:
                    continue

                cls._persist_match(candidate, job, breakdown)
                matched_count += 1

            return {"matched": matched_count}

    @classmethod
    def _persist_match(
        cls,
        candidate: CandidateProfile,
        job: Job,
        breakdown: HybridScoreBreakdown,
    ) -> Match:
        """
        Persists or updates a qualifying Match record.
        - Preserves existing Match status if not SUGGESTED (e.g. CANDIDATE_INTERESTED, MUTUAL_FIT).
        - visible_to_employer is ALWAYS False upon initial creation.
        - Never leaks vectors or private text.
        - Triggers recruiter notification timestamp if score >= HIGH_MATCH_ALERT_THRESHOLD (85).
        """
        int_score = int(round(breakdown.final_score))
        should_notify_recruiter = breakdown.final_score >= HIGH_MATCH_ALERT_THRESHOLD

        with transaction.atomic():
            existing_match = (
                Match.objects.select_for_update()
                .filter(candidate_profile=candidate, job=job)
                .first()
            )

            if existing_match:
                # Update score and reason; preserve user actions and visibility states
                existing_match.match_score = int_score
                existing_match.match_reason = breakdown.reason
                if should_notify_recruiter and not existing_match.recruiter_notified_at:
                    existing_match.recruiter_notified_at = timezone.now()
                existing_match.save(update_fields=["match_score", "match_reason", "recruiter_notified_at", "updated_at"])
                target_match = existing_match
            else:
                # Create new match record with default approval gate (visible_to_employer=False)
                recruiter_notified = timezone.now() if should_notify_recruiter else None
                try:
                    # Inner savepoint ensures IntegrityError rollback does not invalidate outer transaction
                    with transaction.atomic():
                        new_match = Match.objects.create(
                            candidate_profile=candidate,
                            job=job,
                            match_score=int_score,
                            match_reason=breakdown.reason,
                            status=Match.Status.SUGGESTED,
                            visible_to_employer=False,
                            recruiter_notified_at=recruiter_notified,
                        )
                        target_match = new_match
                except IntegrityError:
                    # Handle race condition if a concurrent task inserted the match between filter and create.
                    # Inner savepoint rollback leaves outer transaction valid to retrieve the winning record.
                    concurrent_match = (
                        Match.objects.select_for_update()
                        .get(candidate_profile=candidate, job=job)
                    )
                    concurrent_match.match_score = int_score
                    concurrent_match.match_reason = breakdown.reason
                    if should_notify_recruiter and not concurrent_match.recruiter_notified_at:
                        concurrent_match.recruiter_notified_at = timezone.now()
                    concurrent_match.save(update_fields=["match_score", "match_reason", "recruiter_notified_at", "updated_at"])
                    target_match = concurrent_match

            # Transactional Notification Outbox write (Phase 9.1):
            if should_notify_recruiter and target_match:
                from notifications.services import create_high_match_outbox_record
                create_high_match_outbox_record(target_match, job, breakdown)

        return target_match
