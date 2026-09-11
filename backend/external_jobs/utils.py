import hashlib
import re
from external_jobs.models import ExternalJob


def classify_remote_type(
    location_str: str | None = None, raw_remote_str: str | None = None
) -> str:
    """
    Conservative remote classification helper.
    Only returns REMOTE if explicit remote evidence exists.
    General location strings or ambiguous descriptions default to UNKNOWN.
    """
    combined = f"{location_str or ''} {raw_remote_str or ''}".strip().lower()

    if not combined:
        return ExternalJob.RemoteType.UNKNOWN

    # Explicit Remote patterns
    remote_patterns = [
        r"\bfully\s+remote\b",
        r"\bremote\s*-\s*us\b",
        r"\bremote\s*-\s*united\s+states\b",
        r"\b100%\s+remote\b",
        r"\bwork\s+from\s+home\b",
        r"^remote$",
        r"\bremote\b",
    ]

    # Explicit Hybrid patterns
    hybrid_patterns = [
        r"\bhybrid\b",
        r"\bpartially\s+remote\b",
        r"\bflexible\s+remote\b",
    ]

    # Explicit Onsite patterns
    onsite_patterns = [
        r"\bonsite\b",
        r"\bon-site\b",
        r"\bin-office\b",
        r"\bwork\s+from\s+office\b",
    ]

    # Check explicit patterns in precedence order
    for pattern in hybrid_patterns:
        if re.search(pattern, combined):
            return ExternalJob.RemoteType.HYBRID

    for pattern in onsite_patterns:
        if re.search(pattern, combined) and not any(re.search(p, combined) for p in remote_patterns[:4]):
            return ExternalJob.RemoteType.ONSITE

    for pattern in remote_patterns:
        if re.search(pattern, combined):
            return ExternalJob.RemoteType.REMOTE

    return ExternalJob.RemoteType.UNKNOWN


def generate_dedup_hash(
    company_name: str,
    title: str,
    country: str | None = "US",
    remote_type: str | None = "UNKNOWN",
    location: str | None = None,
) -> str:
    """
    Generates a normalized SHA256 hash used as a SECONDARY potential duplicate detection flag.
    Note: This is NOT an authoritative primary identity or an automatic deletion trigger.
    """
    c_name = (company_name or "").strip().lower()
    t_name = (title or "").strip().lower()
    ctry = (country or "us").strip().lower()
    rtype = (remote_type or "unknown").strip().lower()
    loc = (location or "").strip().lower()

    raw_key = f"{c_name}|{t_name}|{ctry}|{rtype}|{loc}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
