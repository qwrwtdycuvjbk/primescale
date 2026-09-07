from datetime import timedelta
from typing import List, Union
from django.utils import timezone

BLOCKED_SALARY_PHRASES = [
    "competitive",
    "doe",
    "negotiable",
    "based on experience",
    "commensurate",
    "tbd",
    "n/a",
]


def is_valid_salary_range(value: str) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    if len(normalized) < 3:
        return False
    if any(p in normalized for p in BLOCKED_SALARY_PHRASES):
        return False
    return any(char.isdigit() for char in normalized)


def default_job_expiry():
    return timezone.now() + timedelta(days=30)


def parse_skills(value: Union[str, List[str], None]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(s).strip() for s in value if str(s).strip()]
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return []
