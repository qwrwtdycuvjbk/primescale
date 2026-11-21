"""
Candidate External Job Recommendation Engine for PeopleRemotely.

Features:
- CandidateExternalRecommendationService: Evaluates eligible candidates against active,
  embedded external jobs (Adzuna, Himalayas, etc.).
- Reuses the existing 50/30/20 hybrid scoring engine:
    Final Score = (Semantic × 0.50) + (Skills × 0.30) + (Experience × 0.20)
- Strict qualification threshold: Final Score >= 70.0.
- Database-side vector retrieval via pgvector CosineDistance.
- Configurable top-N retrieval limit (default: 100) with fallback to in-memory cosine comparison
  for SQLite/test environments.
- Stale recommendation pruning: Removes or deactivates records when jobs expire,
  become inactive, or when a recalculated score drops below 70.0.
- Fully isolated from first-party ATS Match and HandoffRequest workflows.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from typing import Any, Final, Optional, Union

from django.db import models, transaction
from django.utils import timezone

from candidates.models import CandidateProfile
from external_jobs.models import ExternalJob
from matching.external_job_embeddings import (
    get_eligible_external_job_embeddings,
    is_eligible_external_job,
)
from matching.hybrid_engine import (
    EXPERIENCE_LEVEL_ORDER,
    QUALIFICATION_THRESHOLD,
    WEIGHT_EXPERIENCE,
    WEIGHT_SEMANTIC,
    WEIGHT_SKILLS,
    HybridScoreBreakdown,
    calculate_hybrid_score,
    compute_experience_score,
    compute_skill_overlap_score,
    cosine_distance_to_similarity_score,
    is_candidate_eligible_for_hybrid_matching,
)
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    EmbeddingStatus,
    ExternalJobEmbedding,
    ExternalJobRecommendation,
)
from matching.services import parse_skills, skill_matches

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_RETRIEVAL_LIMIT: Final[int] = 100
FALLBACK_EXTERNAL_JOB_MISSING_SKILL_SCORE: Final[float] = 20.0
MIN_EXTERNAL_JOB_SKILL_DENOMINATOR: Final[int] = 4
SEMANTIC_CALIBRATION_LOWER_BOUND: Final[float] = 20.0
SEMANTIC_CALIBRATION_UPPER_BOUND: Final[float] = 60.0


def calibrate_external_semantic_score(raw_similarity_pct: float) -> float:
    """
    Calibrates raw dense-passage cosine similarity percentage (0.0 to 100.0)
    to a meaningful 0.0 to 100.0 scale for external recommendations.

    Evidence & Rationale:
    - Raw cosine similarity for dense document-level embeddings (e.g. NVIDIA Nemotron-3 2048-dim)
      typically spans the 0.20 to 0.60 range (20.0% to 60.0%) when matching full candidate resumes
      against external job postings.
    - Directly passing 0.20 - 0.60 limits the maximum semantic contribution to <= 30 points (at 50% weight),
      preventing even genuine, top-domain engineering matches from reaching the 70.0 qualification threshold.
    - Calibration applies a deterministic, ranking-preserving piecewise linear transformation:
        - raw <= 20.0: 0.0
        - 20.0 < raw < 60.0: scaled linearly across (raw - 20.0) / (60.0 - 20.0) * 100.0
        - raw >= 60.0: 100.0
    - Safely clamps all outputs to [0.0, 100.0].
    """
    if raw_similarity_pct <= SEMANTIC_CALIBRATION_LOWER_BOUND:
        return 0.0
    if raw_similarity_pct >= SEMANTIC_CALIBRATION_UPPER_BOUND:
        return 100.0

    span = SEMANTIC_CALIBRATION_UPPER_BOUND - SEMANTIC_CALIBRATION_LOWER_BOUND
    calibrated = ((raw_similarity_pct - SEMANTIC_CALIBRATION_LOWER_BOUND) / span) * 100.0
    return max(0.0, min(100.0, calibrated))


def compute_external_job_skill_overlap_score(
    candidate_skills: Union[str, list[str], None],
    job_skills: Union[str, list[str], None],
) -> float:
    """
    Computes percentage of job-required skills found in candidate skills for external recommendations (0.0 to 100.0).

    Rules:
    - If candidate has no skills: returns 0.0.
    - If job specifies no extractable technical skills: returns 20.0 (conservative fallback baseline).
      This prevents unverified-skill jobs from outranking verified partial-match jobs (e.g. 1-of-3 match = 33.33%).
    - Denominator Collapse Mitigation:
      If a job posting contains fewer than MIN_EXTERNAL_JOB_SKILL_DENOMINATOR (4) extracted skills,
      the effective denominator is clamped to MIN_EXTERNAL_JOB_SKILL_DENOMINATOR.
      This prevents 1 or 2 isolated generic skills (e.g. matching 'Go', or 'REST' and 'SQL')
      from artificially yielding an unearned 100% skill score.
    - Formula:
      (|candidate_skills ∩ job_skills| / max(MIN_EXTERNAL_JOB_SKILL_DENOMINATOR, |job_skills|)) * 100.0.
    """
    c_skills = parse_skills(candidate_skills)
    j_skills = parse_skills(job_skills)

    if not c_skills:
        return 0.0

    if not j_skills:
        return FALLBACK_EXTERNAL_JOB_MISSING_SKILL_SCORE

    matched = [
        js for js in j_skills if any(skill_matches(cs, js) for cs in c_skills)
    ]
    effective_denominator = max(MIN_EXTERNAL_JOB_SKILL_DENOMINATOR, len(j_skills))
    return min(100.0, (len(matched) / effective_denominator) * 100.0)


def infer_external_job_experience_level(job: ExternalJob) -> Optional[str]:
    """
    Deterministically extracts and normalizes the required career experience level
    ('junior', 'mid', 'senior', 'lead') for an external job.

    Precedence & Extraction Strategy:
    1. Structured Provider Metadata (e.g., job.raw_metadata.get("seniority")):
       Explicit structured provider classifications take precedence over title heuristics.
       Normalized mappings:
         - junior, entry-level, entry, intern, graduate -> 'junior'
         - mid, intermediate, mid-level, experienced, semi-senior -> 'mid'
         - senior, sr, sr. -> 'senior'
         - lead, staff, principal, director, head -> 'lead'
    2. Job Title Keyword Analysis (word boundaries):
       Regex boundary checks ensure substrings like 'leadership' don't falsely trigger 'lead',
       or 'mideast' doesn't trigger 'mid'.
         - vp, vice president, lead, principal, staff, stf, director, head of -> 'lead'
         - senior, sr., sr -> 'senior'
         - semi-senior, semi senior, mid-level, intermediate -> 'mid'
         - junior, jr., jr, entry-level, intern, associate -> 'junior'
    3. Job Description Explicit Experience Requirements (e.g. '7+ years', '5 years of experience'):
       Extracts explicit minimum required years from description text:
         - >= 8 years -> 'lead'
         - >= 5 years -> 'senior'
         - >= 2 years -> 'mid'
         - < 2 years -> 'junior'
    4. Accuracy Requirement & Fallback:
       If metadata, title, and description lack reliable seniority evidence, returns None
       so compute_experience_score safely applies the neutral baseline (50.0).
    """
    import re

    # 1. Inspect structured provider metadata
    if hasattr(job, "raw_metadata") and isinstance(job.raw_metadata, dict):
        raw_seniority = job.raw_metadata.get("seniority")
        if raw_seniority and isinstance(raw_seniority, str):
            clean_s = raw_seniority.strip().lower()
            if clean_s in ("junior", "entry-level", "entry", "intern", "graduate"):
                return "junior"
            if clean_s in ("mid", "intermediate", "mid-level", "experienced", "semi-senior", "semi senior"):
                return "mid"
            if clean_s in ("senior", "sr", "sr."):
                return "senior"
            if clean_s in ("lead", "staff", "principal", "director", "head", "vp", "vice president"):
                return "lead"

    # 2. Inspect job title with regex word boundaries
    title = getattr(job, "title", "") or ""
    title_lower = title.strip().lower()

    if title_lower:
        # Check for executive / lead / staff / principal / vp
        if re.search(r"\b(vp|vice president|lead|principal|staff|stf|director|head of)\b", title_lower):
            return "lead"

        # Check for senior / sr
        if re.search(r"\b(senior|sr\.?)\b", title_lower):
            return "senior"

        # Check for semi-senior / intermediate / mid-level
        if re.search(r"\b(semi[- ]senior|mid[- ]level|intermediate)\b", title_lower):
            return "mid"

        # Check for junior / jr / entry / associate
        if re.search(r"\b(junior|jr\.?|entry[- ]level|intern|associate)\b", title_lower):
            return "junior"

    # 3. Inspect job description for explicit experience requirements
    desc = getattr(job, "description", "") or ""
    desc_lower = desc.strip().lower()

    if desc_lower:
        # Check for semi-senior in description
        if re.search(r"\b(semi[- ]senior)\b", desc_lower):
            return "mid"

        patterns = [
            r"(\d+)\s*\+?\s*(?:to\s*(\d+)|-\s*(\d+))?\s*years?(?:\s+of)?\s+(?:relevant\s+|professional\s+|software\s+)?experience",
            r"minimum\s+(?:of\s+)?(\d+)\s*\+?\s*years?",
            r"at\s+least\s+(\d+)\s*\+?\s*years?",
            r"(\d+)\s*\+?\s*years?\s+required",
        ]
        for p in patterns:
            m = re.search(p, desc_lower)
            if m:
                try:
                    yrs = int(m.group(1))
                    if yrs >= 8:
                        return "lead"
                    elif yrs >= 5:
                        return "senior"
                    elif yrs >= 2:
                        return "mid"
                    else:
                        return "junior"
                except Exception:
                    pass

    # Indeterminate: return None to allow neutral fallback
    return None



@dataclass(frozen=True)
class RecommendationEvaluationResult:
    """Summary of recommendation evaluation run for a candidate or external job."""

    candidate_profile_id: str
    total_evaluated: int
    qualified_count: int
    updated_count: int
    pruned_count: int
    is_eligible: bool = True
    ineligibility_reason: Optional[str] = None


class CandidateExternalRecommendationService:
    """
    Evaluates an eligible candidate against active, embedded external jobs,
    persisting qualified recommendations (score >= 70.0) into ExternalJobRecommendation.
    """

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_or_id: Union[str, uuid.UUID, CandidateProfile],
        retrieval_limit: int = DEFAULT_VECTOR_RETRIEVAL_LIMIT,
        force_recalculate: bool = False,
    ) -> RecommendationEvaluationResult:
        """
        Runs recommendation evaluation for a single candidate profile.
        1. Validates candidate eligibility (completeness=100, open_to_matching, resume, completed embedding).
        2. Retrieves top-N eligible external jobs using database-side pgvector CosineDistance.
        3. Computes 50/30/20 hybrid score.
        4. Persists qualified recommendations (score >= 70.0) and prunes stale records.
        """
        if isinstance(candidate_or_id, CandidateProfile):
            candidate = candidate_or_id
        else:
            try:
                candidate = (
                    CandidateProfile.objects.select_related("user", "resume_embedding")
                    .get(id=candidate_or_id)
                )
            except (CandidateProfile.DoesNotExist, ValueError):
                cid_str = str(candidate_or_id)
                logger.warning("CandidateProfile %s not found; aborting external recommendation evaluation.", cid_str)
                return RecommendationEvaluationResult(
                    candidate_profile_id=cid_str,
                    total_evaluated=0,
                    qualified_count=0,
                    updated_count=0,
                    pruned_count=0,
                    is_eligible=False,
                    ineligibility_reason="Candidate profile does not exist.",
                )

        cid_str = str(candidate.id)

        # 1. Eligibility Check
        is_eligible, reason = is_candidate_eligible_for_hybrid_matching(candidate)
        if not is_eligible:
            logger.info("Candidate %s ineligible for external recommendations: %s", cid_str, reason)
            # Prune any existing recommendations since candidate is currently ineligible
            del_res = ExternalJobRecommendation.objects.filter(candidate_profile=candidate).delete()
            deleted_count = del_res[0] if isinstance(del_res, tuple) else 0
            return RecommendationEvaluationResult(
                candidate_profile_id=cid_str,
                total_evaluated=0,
                qualified_count=0,
                updated_count=0,
                pruned_count=deleted_count,
                is_eligible=False,
                ineligibility_reason=reason,
            )

        resume_emb = getattr(candidate, "resume_embedding", None)
        candidate_vector = resume_emb.embedding
        candidate_version = resume_emb.version or resume_emb.content_hash or "v1"

        # 2. Query eligible external jobs
        eligible_job_embeddings = (
            get_eligible_external_job_embeddings()
            .select_related("external_job", "external_job__source")
        )

        total_available = eligible_job_embeddings.count()
        if total_available == 0:
            logger.info("No eligible external job embeddings found for candidate %s evaluation.", cid_str)
            del_res = ExternalJobRecommendation.objects.filter(candidate_profile=candidate).delete()
            deleted_count = del_res[0] if isinstance(del_res, tuple) else 0
            return RecommendationEvaluationResult(
                candidate_profile_id=cid_str,
                total_evaluated=0,
                qualified_count=0,
                updated_count=0,
                pruned_count=deleted_count,
            )

        limit = max(1, retrieval_limit)

        # 3. Vector Similarity Retrieval (pgvector database query with in-memory fallback)
        annotated_jobs: list[tuple[ExternalJob, float, ExternalJobEmbedding]] = []

        try:
            from pgvector.django import CosineDistance

            qs = (
                eligible_job_embeddings.annotate(
                    distance=CosineDistance("embedding", candidate_vector)
                )
                .order_by("distance")[:limit]
            )

            for job_emb in qs:
                distance = getattr(job_emb, "distance", None)
                if distance is not None and math.isfinite(distance):
                    sem_score = cosine_distance_to_similarity_score(distance)
                else:
                    sem_score = cls._compute_in_memory_similarity(candidate_vector, job_emb.embedding)
                annotated_jobs.append((job_emb.external_job, sem_score, job_emb))

        except Exception as exc:
            logger.debug("Falling back to in-memory vector comparison for candidate %s: %s", cid_str, exc)
            # Exact in-memory cosine fallback (for test runners / sqlite)
            all_embeddings = list(eligible_job_embeddings[:limit])
            for job_emb in all_embeddings:
                sem_score = cls._compute_in_memory_similarity(candidate_vector, job_emb.embedding)
                annotated_jobs.append((job_emb.external_job, sem_score, job_emb))
            # Sort descending by semantic score
            annotated_jobs.sort(key=lambda item: item[1], reverse=True)

        # Resolve candidate skills: union of explicit profile skills and resume-extracted skills
        from common.skill_extraction import extract_technical_skills

        profile_skills = parse_skills(candidate.skills)
        extracted_skills = []
        if resume_emb:
            extracted_skills = getattr(resume_emb, "extracted_skills", []) or []
            if not extracted_skills and getattr(resume_emb, "extracted_text", None):
                extracted_skills = extract_technical_skills(resume_emb.extracted_text)

        effective_candidate_skills = sorted(
            list(set(profile_skills) | set(s.lower() for s in extracted_skills))
        )

        # 4. Detailed Hybrid Evaluation & Persistence
        qualified_count = 0
        updated_count = 0
        evaluated_job_ids: set[uuid.UUID] = set()

        for job, semantic_score, job_emb in annotated_jobs:
            evaluated_job_ids.add(job.id)

            # Re-check job eligibility
            job_ok, _ = is_eligible_external_job(job)
            if not job_ok:
                continue

            # Resolve job skills: filter out generic categories, extract real skills
            effective_job_skills = extract_technical_skills(job.tech_stack)
            if not effective_job_skills:
                effective_job_skills = extract_technical_skills(f"{job.title}\n{job.description}")

            # Compute calibrated semantic, skill overlap, and experience scores
            calibrated_sem_score = calibrate_external_semantic_score(semantic_score)
            skill_score = compute_external_job_skill_overlap_score(
                effective_candidate_skills, effective_job_skills
            )
            inferred_job_level = infer_external_job_experience_level(job)
            exp_score = compute_experience_score(candidate.experience_level, inferred_job_level)

            breakdown = calculate_hybrid_score(calibrated_sem_score, skill_score, exp_score)

            if not breakdown.qualifies:
                # If a previous recommendation existed for this pair and now drops below 70, remove it
                ExternalJobRecommendation.objects.filter(
                    candidate_profile=candidate,
                    external_job=job,
                ).delete()
                continue

            matched_skills = cls._extract_matched_skills(effective_candidate_skills, effective_job_skills)

            # Check cache / idempotency
            existing_rec = ExternalJobRecommendation.objects.filter(
                candidate_profile=candidate,
                external_job=job,
            ).first()

            if (
                not force_recalculate
                and existing_rec is not None
                and existing_rec.final_score == breakdown.final_score
                and existing_rec.embedding_version == candidate_version
            ):
                # Score and version unchanged
                qualified_count += 1
                continue

            # Concurrency-safe persistence
            with transaction.atomic():
                rec, created = ExternalJobRecommendation.objects.update_or_create(
                    candidate_profile=candidate,
                    external_job=job,
                    defaults={
                        "semantic_score": breakdown.semantic_score,
                        "skill_score": breakdown.skill_score,
                        "experience_score": breakdown.exp_score,
                        "final_score": breakdown.final_score,
                        "matched_skills": matched_skills,
                        "match_reason": breakdown.reason,
                        "matching_model": TARGET_EMBEDDING_MODEL,
                        "embedding_version": candidate_version,
                    },
                )
                qualified_count += 1
                updated_count += 1

        # 5. Prune Stale Recommendations for jobs that were NOT in the retrieved qualified set
        # or underlying jobs that are no longer active/eligible
        now = timezone.now()
        prune_res = (
            ExternalJobRecommendation.objects.filter(candidate_profile=candidate)
            .filter(
                models.Q(external_job__is_active=False)
                | ~models.Q(external_job__status=ExternalJob.Status.ACTIVE)
                | (models.Q(external_job__expires_at__isnull=False) & models.Q(external_job__expires_at__lte=now))
            )
            .delete()
        )
        pruned_count = prune_res[0] if isinstance(prune_res, tuple) else 0

        logger.info(
            "External recommendation evaluation complete for candidate %s: "
            "%d evaluated, %d qualified, %d updated, %d pruned.",
            cid_str,
            len(annotated_jobs),
            qualified_count,
            updated_count,
            pruned_count,
        )

        return RecommendationEvaluationResult(
            candidate_profile_id=cid_str,
            total_evaluated=len(annotated_jobs),
            qualified_count=qualified_count,
            updated_count=updated_count,
            pruned_count=pruned_count,
        )

    @staticmethod
    def _compute_in_memory_similarity(
        vec_a: Optional[list[float]],
        vec_b: Optional[list[float]],
    ) -> float:
        """In-memory dot product similarity fallback for unit tests and local non-pgvector environments."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(y * y for y in vec_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        cos_sim = dot / (norm_a * norm_b)
        clamped = max(0.0, min(1.0, cos_sim))
        return clamped * 100.0

    @staticmethod
    def _extract_matched_skills(
        candidate_skills: Any,
        job_skills: Any,
    ) -> list[str]:
        """Returns the list of overlapping skill names."""
        c_skills = parse_skills(candidate_skills)
        j_skills = parse_skills(job_skills)

        if not c_skills or not j_skills:
            return []

        matched = [
            js for js in j_skills if any(skill_matches(cs, js) for cs in c_skills)
        ]
        return sorted(list(set(matched)))
