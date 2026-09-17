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

    # Strong explicit Remote patterns
    strong_remote_patterns = [
        r"\bfully\s+remote\b",
        r"\b100%\s+remote\b",
        r"\b100\s*%\s*remote\b",
        r"\bremote\s*[-–—,]\s*(?:us|usa|united\s+states)\b",
        r"\bwork\s+from\s+anywhere\b",
        r"\bwork-from-anywhere\b",
        r"\bwork\s+from\s+home\b",
        r"\bwork-from-home\b",
        r"\bwork\s+remotely\b",
        r"\bworking\s+remotely\b",
        r"\btelecommut(?:er|ing|e|ers)\b",
        r"\btelework(?:ing|er|ers)?\b",
        r"\bremote\s+(?:role|opportunity|position|job|work|working)\b",
        r"\bwfh\b",
    ]

    # Explicit Hybrid patterns
    hybrid_patterns = [
        r"\bhybrid\b",
        r"\bpartially\s+remote\b",
        r"\bpartial\s+remote\b",
        r"\bflexible\s+remote\b",
    ]

    # Explicit Onsite patterns
    onsite_patterns = [
        r"\bonsite\b",
        r"\bon-site\b",
        r"\bin-office\b",
        r"\bin\s+office\b",
        r"\bwork\s+from\s+office\b",
        r"\bwork-from-office\b",
    ]

    # General Remote patterns
    general_remote_patterns = [
        r"^remote$",
        r"\bremote\b",
    ]

    # Check explicit patterns in precedence order
    for pattern in hybrid_patterns:
        if re.search(pattern, combined):
            return ExternalJob.RemoteType.HYBRID

    for pattern in strong_remote_patterns:
        if re.search(pattern, combined):
            return ExternalJob.RemoteType.REMOTE

    for pattern in onsite_patterns:
        if re.search(pattern, combined):
            return ExternalJob.RemoteType.ONSITE

    for pattern in general_remote_patterns:
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


DEPARTMENT_DEFINITIONS = [
    {
        "code": "data-ai",
        "name": "Data & AI",
        "regex": r"\b(data\s+scientist|data\s+analyst|machine\s+learning|ml\s+engineer|ai\s+engineer|artificial\s+intelligence|bi\s+developer|business\s+intelligence|big\s+data|deep\s+learning|nlp\s+engineer|nlp|data\s+architect|data\s+engineer|ai\s+researcher)\b",
    },
    {
        "code": "devops-cloud",
        "name": "DevOps & Cloud",
        "regex": r"\b(devops|cloud\s+engineer|site\s+reliability|sre\b|platform\s+engineer|aws\s+engineer|azure\s+engineer|infrastructure|kubernetes|systems?\s+engineer|cloud\s+architect|cloud\s+developer|sysadmin)\b",
    },
    {
        "code": "qa-testing",
        "name": "QA & Testing",
        "regex": r"\b(qa\s+engineer|test\s+engineer|automation\s+tester|software\s+tester|sdet\b|quality\s+assurance|test\s+analyst|manual\s+tester|qa\s+lead|qa\s+analyst|testing)\b",
    },
    {
        "code": "cybersecurity",
        "name": "Cybersecurity",
        "regex": r"\b(cybersecurity|security\s+engineer|soc\s+analyst|information\s+security|infosec\b|appsec\b|penetration\s+test|pen\s+tester|security\s+architect|cyber\s+security)\b",
    },
    {
        "code": "product",
        "name": "Product",
        "regex": r"\b(product\s+manager|product\s+owner|technical\s+product\s+manager|head\s+of\s+product|vp\s+of\s+product|director\s+of\s+product|apm\b)\b",
    },
    {
        "code": "design",
        "name": "Design",
        "regex": r"\b(ui\s+designer|ux\s+designer|product\s+designer|ux/ui|ui/ux|visual\s+designer|interaction\s+designer|graphic\s+designer|design\s+lead)\b",
    },
    {
        "code": "project-management",
        "name": "Project Management",
        "regex": r"\b(project\s+manager|scrum\s+master|agile\s+coach|program\s+manager|delivery\s+manager|pmo\b)\b",
    },
    {
        "code": "business-operations",
        "name": "Business & Operations",
        "regex": r"\b(business\s+analyst|operations\s+manager|sap\s+consultant|sap\s+rar|erp\s+consultant|salesforce\s+administrator|management\s+consultant|sap\s+mdg|sap\s+srm|operations|consultant)\b",
    },
    {
        "code": "software-engineering",
        "name": "Software Engineering",
        "regex": r"\b(software\s+engineer|software\s+developer|backend|frontend|front-end|full\s*stack|developer|programmer|\.net|python|java\b|react|django|node|javascript|typescript|c\+\+|golang|ruby|php\b|web\s+developer|mobile\s+developer|ios\s+developer|android\s+developer)\b",
    },
]


def classify_job_department(
    title: str | None = None,
    tech_stack: list | None = None,
    description: str | None = None,
) -> str:
    """
    Centralized deterministic department classification helper.
    Classifies a job into a standard department based on title and metadata.
    """
    text = (title or "").strip().lower()
    for dept in DEPARTMENT_DEFINITIONS:
        if re.search(dept["regex"], text):
            return dept["name"]

    if tech_stack:
        combined_tech = " ".join(
            [str(t).replace("-", " ") for t in tech_stack]
        ).lower()
        for dept in DEPARTMENT_DEFINITIONS:
            if re.search(dept["regex"], combined_tech):
                return dept["name"]

    if description:
        desc_text = (description or "")[:1000].lower()
        for dept in DEPARTMENT_DEFINITIONS:
            if re.search(dept["regex"], desc_text):
                return dept["name"]

    return "Other"


def get_department_q_filter(department_input: str):
    """
    Returns a Django Q filter corresponding to a department code or name.
    """
    from django.db.models import Q

    val = (department_input or "").strip().lower()
    if not val or val in ("all", "all departments", "*"):
        return Q()

    for dept in DEPARTMENT_DEFINITIONS:
        if val in (
            dept["code"].lower(),
            dept["name"].lower(),
            dept["code"].replace("-", " ").lower(),
        ):
            return Q(title__iregex=dept["regex"])

    if val in ("other", "others"):
        q_ex = Q()
        for dept in DEPARTMENT_DEFINITIONS:
            q_ex |= Q(title__iregex=dept["regex"])
        return ~q_ex

    return Q(title__icontains=department_input)
