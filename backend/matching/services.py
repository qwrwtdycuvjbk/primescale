import logging
import re
from typing import List, Optional, Union
from django.db import transaction
from django.utils import timezone

from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

from candidates.models import CandidateProfile
from jobs.models import Job
from .models import Match

MIN_MATCH_SCORE = 85
EXPERIENCE_LEVEL_ORDER = ["junior", "mid", "senior", "lead"]


def parse_skills(input_val: Union[str, List[str], None]) -> List[str]:
    """
    Parses string or list of skills into a deduplicated lowercase list.
    Splits on comma, semicolon, newline, pipe.
    """
    if not input_val:
        return []
    if isinstance(input_val, list):
        raw = ",".join(str(s) for s in input_val)
    else:
        raw = str(input_val)

    tokens = re.split(r"[,;\n|]", raw)
    seen = set()
    result = []
    for s in tokens:
        cleaned = s.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def skill_matches(candidate_skill: str, job_skill: str) -> bool:
    """
    Case-insensitive substring match matching TypeScript src/lib/matching.ts:
    candidateSkill === jobSkill || candidateSkill.includes(jobSkill) || jobSkill.includes(candidateSkill)
    """
    cs = candidate_skill.strip().lower()
    js = job_skill.strip().lower()
    if not cs or not js:
        return False
    return cs == js or js in cs or cs in js


def compute_skill_overlap_score(
    candidate_skills: Union[str, List[str], None],
    job_skills: Union[str, List[str], None],
) -> int:
    """
    Percentage of job-required skills found in candidate skills.
    If job requires no skills -> 40
    If candidate has no skills -> 0
    Returns integer percentage: round((matched / job_skills.length) * 100)
    """
    c_skills = parse_skills(candidate_skills)
    j_skills = parse_skills(job_skills)

    if not j_skills:
        return 40
    if not c_skills:
        return 0

    matched = [
        js for js in j_skills if any(skill_matches(cs, js) for cs in c_skills)
    ]
    return round((len(matched) / len(j_skills)) * 100)


def compute_experience_score(
    candidate_level: Optional[str],
    job_level: Optional[str],
) -> int:
    """
    100 -> candidate level >= job level
    70  -> one level below (diff == -1)
    40  -> two or more levels below (diff <= -2)
    50  -> unknown or missing levels
    """
    if not candidate_level or not job_level:
        return 50

    cl = candidate_level.strip().lower()
    jl = job_level.strip().lower()

    if cl not in EXPERIENCE_LEVEL_ORDER or jl not in EXPERIENCE_LEVEL_ORDER:
        return 50

    c_idx = EXPERIENCE_LEVEL_ORDER.index(cl)
    j_idx = EXPERIENCE_LEVEL_ORDER.index(jl)
    diff = c_idx - j_idx

    if diff >= 0:
        return 100
    if diff == -1:
        return 70
    return 40


def combined_match_score(skill_score: int, exp_score: int) -> int:
    """
    Formula: round(skillScore * 0.7 + expScore * 0.3)
    """
    return round(skill_score * 0.7 + exp_score * 0.3)


def resolve_match_status(current_status: str, requested_status: str) -> str:
    """
    Mutual fit state machine:
    candidate_interested + employer_shortlisted -> mutual_fit
    employer_shortlisted + candidate_interested -> mutual_fit
    rejected -> rejected
    """
    if requested_status == Match.Status.REJECTED:
        return Match.Status.REJECTED

    is_mutual_fit = (
        (requested_status == Match.Status.EMPLOYER_SHORTLISTED and current_status == Match.Status.CANDIDATE_INTERESTED)
        or (requested_status == Match.Status.CANDIDATE_INTERESTED and current_status == Match.Status.EMPLOYER_SHORTLISTED)
    )

    if is_mutual_fit:
        return Match.Status.MUTUAL_FIT
    return requested_status


from .hybrid_engine import (
    HybridMatchingEngine,
    calculate_hybrid_score,
    is_candidate_eligible_for_hybrid_matching,
    is_job_eligible_for_hybrid_matching,
)


def run_hybrid_matching_for_candidate(candidate_profile_id: str) -> dict:
    """
    Direct interface to run Phase 7 Hybrid Matching for a candidate profile.
    Requires completed candidate resume embedding and matches eligible first-party jobs.
    """
    return HybridMatchingEngine.run_matching_for_candidate(candidate_profile_id)


def run_hybrid_matching_for_job(job_id: str) -> dict:
    """
    Direct interface to run Phase 7 Hybrid Matching for a first-party job.
    Requires completed job embedding and matches eligible candidates.
    """
    return HybridMatchingEngine.run_matching_for_job(job_id)


def run_matching_for_candidate(candidate_profile_id: str) -> dict:
    """
    Runs matching for a single candidate profile across active jobs.
    If the candidate and jobs possess eligible embeddings, executes the Phase 7 Hybrid Engine.
    Otherwise gracefully uses legacy skill/experience scoring for backward compatibility.
    """
    try:
        candidate = CandidateProfile.objects.select_related("user", "resume_embedding").get(
            id=candidate_profile_id,
            open_to_matching=True,
            profile_complete=True,
        )
    except CandidateProfile.DoesNotExist:
        return {"matched": 0}

    # If candidate has an active embedding, execute Hybrid Matching Engine
    cand_eligible, cand_reason = is_candidate_eligible_for_hybrid_matching(candidate)
    if cand_eligible:
        return HybridMatchingEngine.run_matching_for_candidate(candidate)

    # If the candidate has an embedding record that is FAILED, PENDING, or STALE,
    # NEVER fall back to legacy matching. It must return 0 matched.
    resume_emb = getattr(candidate, "resume_embedding", None)
    if resume_emb is not None:
        logger.warning(
            "Candidate %s has an incomplete, failed, or stale resume embedding (%s). "
            "Legacy fallback is strictly prohibited: %s",
            candidate.id,
            resume_emb.status,
            cand_reason,
        )
        return {"matched": 0, "reason": cand_reason}

    # Legacy fallback for environments / tests without embeddings
    active_jobs = Job.objects.filter(status=Job.Status.ACTIVE)
    matched_count = 0

    for job in active_jobs:
        skill_score = compute_skill_overlap_score(candidate.skills, job.tech_stack)
        exp_score = compute_experience_score(candidate.experience_level, job.experience_level)
        score = combined_match_score(skill_score, exp_score)

        if score < MIN_MATCH_SCORE:
            continue

        reason = f"Skills overlap at {skill_score}% with required stack."

        match, created = Match.objects.update_or_create(
            candidate_profile=candidate,
            job=job,
            defaults={
                "match_score": score,
                "match_reason": reason,
                "status": Match.Status.SUGGESTED,
                "visible_to_employer": False,
            },
        )
        matched_count += 1
        notify_recruiters_for_high_match(str(match.id))

    return {"matched": matched_count}


def run_matching_for_job(job_id: str) -> dict:
    """
    Runs matching for a single active job across candidates.
    If the job possesses an eligible embedding, executes the Phase 7 Hybrid Engine.
    Otherwise gracefully uses legacy skill/experience scoring for backward compatibility.
    """
    try:
        job = Job.objects.select_related("company", "posted_by", "job_embedding").get(
            id=job_id,
            status=Job.Status.ACTIVE,
        )
    except Job.DoesNotExist:
        return {"matched": 0}

    # If job has an active embedding, execute Hybrid Matching Engine
    job_eligible, job_reason = is_job_eligible_for_hybrid_matching(job)
    if job_eligible:
        return HybridMatchingEngine.run_matching_for_job(job)

    # If the job has an embedding record that is FAILED, PENDING, or STALE,
    # NEVER fall back to legacy matching. It must return 0 matched.
    job_emb = getattr(job, "job_embedding", None)
    if job_emb is not None:
        logger.warning(
            "Job %s has an incomplete, failed, or stale job embedding (%s). "
            "Legacy fallback is strictly prohibited: %s",
            job.id,
            job_emb.status,
            job_reason,
        )
        return {"matched": 0, "reason": job_reason}

    # Legacy fallback for environments / tests without embeddings
    candidates = CandidateProfile.objects.filter(
        open_to_matching=True,
        profile_complete=True,
    )
    matched_count = 0

    for candidate in candidates:
        skill_score = compute_skill_overlap_score(candidate.skills, job.tech_stack)
        exp_score = compute_experience_score(candidate.experience_level, job.experience_level)
        score = combined_match_score(skill_score, exp_score)

        if score < MIN_MATCH_SCORE:
            continue

        reason = f"Skills overlap at {skill_score}% with required stack."

        match, created = Match.objects.update_or_create(
            candidate_profile=candidate,
            job=job,
            defaults={
                "match_score": score,
                "match_reason": reason,
                "status": Match.Status.SUGGESTED,
                "visible_to_employer": False,
            },
        )
        matched_count += 1
        notify_recruiters_for_high_match(str(match.id))

    return {"matched": matched_count}


def notify_recruiters_for_high_match(match_id: str):
    """
    Idempotently records recruiter notification timestamp for matches with score >= 85.
    Deprecated in Phase 9.10: legacy Celery tasks are no longer scheduled;
    high-match alerts are exclusively managed by the transactional NotificationOutbox.
    """
    try:
        match = Match.objects.get(id=match_id)
        if match.match_score >= MIN_MATCH_SCORE:
            if not match.recruiter_notified_at:
                match.recruiter_notified_at = timezone.now()
                match.save(update_fields=["recruiter_notified_at", "updated_at"])
    except Match.DoesNotExist:
        pass


def send_recruiter_high_match_notification(match_id: str) -> dict:
    """
    Deprecated and defused in Phase 9.10 in favor of transactional NotificationOutbox.
    High-match notifications are exclusively dispatched via NotificationOutbox.
    This helper is defused and never calls send_mail().
    """
    logger.info("send_recruiter_high_match_notification is retired in Phase 9.10; send_mail suppressed for %s", match_id)
    return {
        "delivered": False,
        "reason": "Retired in favor of NotificationOutbox; send_mail suppressed.",
        "match_id": str(match_id),
    }


def notify_recruiters_candidate_interested(match_id: str):
    """
    Triggers alert when candidate marks interest.
    """
    # In future phases this dispatches Resend email via Celery task.
    pass
