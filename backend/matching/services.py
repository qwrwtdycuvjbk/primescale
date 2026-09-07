import re
from typing import List, Optional, Union
from django.db import transaction
from django.utils import timezone

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


def run_matching_for_candidate(candidate_profile_id: str) -> dict:
    """
    Runs matching for a single candidate profile across all active jobs.
    Upserts match records for scores >= MIN_MATCH_SCORE.
    """
    try:
        candidate = CandidateProfile.objects.select_related("user").get(
            id=candidate_profile_id,
            open_to_matching=True,
            profile_complete=True,
        )
    except CandidateProfile.DoesNotExist:
        return {"matched": 0}

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
    Runs matching for a single active job across all open & complete candidates.
    Upserts match records for scores >= MIN_MATCH_SCORE.
    """
    try:
        job = Job.objects.select_related("company", "posted_by").get(
            id=job_id,
            status=Job.Status.ACTIVE,
        )
    except Job.DoesNotExist:
        return {"matched": 0}

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
    """
    try:
        match = Match.objects.get(id=match_id)
        if match.match_score >= MIN_MATCH_SCORE and not match.recruiter_notified_at:
            match.recruiter_notified_at = timezone.now()
            match.save(update_fields=["recruiter_notified_at", "updated_at"])
    except Match.DoesNotExist:
        pass


def notify_recruiters_candidate_interested(match_id: str):
    """
    Triggers alert when candidate marks interest.
    """
    # In future phases this dispatches Resend email via Celery task.
    pass
