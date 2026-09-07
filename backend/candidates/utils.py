from typing import Any, Dict, List, Optional, Union


def parse_skills_list(value: Union[str, List[str], None]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return []


def calculate_profile_completeness(data: Dict[str, Any]) -> int:
    """
    Exact 15-check completeness calculation ported from src/lib/profile-completeness.ts.
    Returns an integer percentage between 0 and 100.
    """
    skills = data.get("skills")
    if isinstance(skills, str):
        has_skills = bool(skills.strip())
    elif isinstance(skills, list):
        has_skills = len(skills) > 0
    else:
        has_skills = False

    role_categories = data.get("role_categories")
    has_role_categories = bool(role_categories and len(role_categories) > 0)

    years_exp = data.get("years_experience")
    has_years_exp = years_exp is not None and years_exp >= 0

    salary_min = data.get("salary_min")
    salary_max = data.get("salary_max")
    has_salary = salary_min is not None or salary_max is not None

    github = (data.get("github_url") or "").strip()
    portfolio = (data.get("portfolio_url") or "").strip()
    has_links = bool(github or portfolio)

    checks = [
        bool((data.get("headline") or "").strip()),
        bool((data.get("phone") or "").strip()),
        bool((data.get("current_title") or "").strip()),
        has_years_exp,
        has_skills,
        has_role_categories,
        bool(data.get("experience_level")),
        bool(data.get("work_authorization")),
        bool(data.get("us_state")),
        has_salary,
        bool((data.get("bio") or "").strip()),
        bool((data.get("resume_url") or "").strip()),
        has_links,
        bool(data.get("availability_status")),
        bool(data.get("preferred_work_type")),
    ]

    filled = sum(1 for c in checks if c)
    return round((filled / len(checks)) * 100)


def is_candidate_profile_complete(data: Dict[str, Any]) -> bool:
    """
    Verifies all mandatory fields are filled:
    headline, phone, current_title, skills, role_categories, and resume_url.
    """
    skills = parse_skills_list(data.get("skills"))
    role_cats = data.get("role_categories") or []

    has_required = bool(
        (data.get("headline") or "").strip()
        and (data.get("phone") or "").strip()
        and (data.get("current_title") or "").strip()
        and len(skills) > 0
        and len(role_cats) > 0
    )
    has_resume = bool((data.get("resume_url") or "").strip())
    return has_required and has_resume
