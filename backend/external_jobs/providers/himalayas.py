import logging
import os
import re
import time
from datetime import datetime, timezone as dt_timezone, timedelta
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from external_jobs.models import ExternalJobSource, ExternalJob
from external_jobs.utils import generate_dedup_hash, clean_html_text, html_to_plain_text

logger = logging.getLogger(__name__)

HIMALAYAS_PROVIDER_CODE = "himalayas"
HIMALAYAS_DISPLAY_NAME = "Himalayas"
HIMALAYAS_BASE_API_URL = "https://himalayas.app/jobs/api"
HIMALAYAS_SEARCH_API_URL = "https://himalayas.app/jobs/api/search"
HIMALAYAS_ATTRIBUTION_URL = "https://himalayas.app"
DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGES = None  # None = fetch all pages until nextCursor is absent
DEFAULT_INGESTION_MAX_DAYS = 7

# Pre-configured occupational query groups for targeted technical coverage
HIMALAYAS_QUERY_GROUPS = {
    "frontend": ["react", "frontend", "typescript", "javascript"],
    "backend": ["python", "django", "backend", "api developer"],
    "fullstack": ["full stack", "fullstack"],
    "java": ["java", "spring boot"],
    "devops": ["devops", "aws", "cloud engineer", "kubernetes"],
}

MAX_RETRIES_PER_PAGE = 4
RETRY_DELAYS = [5, 10, 20, 40]
INTER_PAGE_DELAY = 1.0  # seconds between successful pagination requests

COUNTRY_NAME_TO_CODE = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "us": "US",
    "india": "IN",
    "canada": "CA",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "germany": "DE",
    "france": "FR",
    "poland": "PL",
    "australia": "AU",
    "brazil": "BR",
    "netherlands": "NL",
    "spain": "ES",
    "italy": "IT",
    "singapore": "SG",
    "japan": "JP",
    "ireland": "IE",
    "switzerland": "CH",
    "sweden": "SE",
    "israel": "IL",
    "mexico": "MX",
    "argentina": "AR",
    "colombia": "CO",
    "philippines": "PH",
    "vietnam": "VN",
    "south africa": "ZA",
    "nigeria": "NG",
    "portugal": "PT",
    "new zealand": "NZ",
    "austria": "AT",
    "belgium": "BE",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "finland": "FI",
    "norway": "NO",
    "romania": "RO",
    "ukraine": "UA",
    "united arab emirates": "AE",
    "uae": "AE",
    "pakistan": "PK",
    "bangladesh": "BD",
    "indonesia": "ID",
    "malaysia": "MY",
}

# Recognized positive categories and category slugs for engineering/technical relevance
HIMALAYAS_POSITIVE_CATEGORIES = {
    "developer",
    "data science",
    "software engineering",
    "engineering",
    "devops",
    "cloud",
    "cybersecurity",
}

HIMALAYAS_POSITIVE_CATEGORY_SLUGS = {
    "software-engineer",
    "software-developer",
    "backend-engineer",
    "backend-developer",
    "frontend-engineer",
    "frontend-developer",
    "full-stack-engineer",
    "full-stack-developer",
    "devops-engineer",
    "cloud-engineer",
    "cloud-architect",
    "infrastructure-engineer",
    "platform-engineer",
    "site-reliability-engineer",
    "security-engineer",
    "security-architect",
    "cyber-security-architect",
    "information-security-architect",
    "machine-learning-engineer",
    "ai-engineer",
    "data-engineer",
    "solutions-architect",
    "technology-architect",
    "enterprise-architect",
    "technical-architect",
    "automation-engineer",
    "ai-automation-engineer",
    "database-administrator",
    "data-scientist",
    "principal-software-engineer",
    "principal-engineer",
    "staff-software-developer",
    "sap-software-developer",
    "sap-integration-engineer",
    "workflow-engineer",
}

# Positive technical title regex patterns
HIMALAYAS_POSITIVE_TITLE_PATTERNS = [
    r"\bsoftware\s+(?:development\s+)?(?:engineer|developer|architect)\b",
    r"\b(?:backend|frontend|full[\s-]?stack)\s+(?:engineer|developer)\b",
    r"\b(?:python|java|javascript|typescript|react|node(?:\.js)?|golang|go|rust|c\+\+|c#|\.net)\s+(?:engineer|developer)\b",
    r"\b(?:cloud|devops|sre|infrastructure|platform)\s+(?:engineer|architect|lead)\b",
    r"\bsite\s+reliability\s+engineer\b",
    r"\b(?:data|machine\s+learning|ml|ai)\s+engineer\b",
    r"\b(?:security|infosec|cybersecurity)\s+(?:engineer|architect)\b",
    r"\b(?:enterprise|technology|systems?|automation)\s+(?:architect|engineer)\b",
    r"\bprincipal\s+(?:architect\s+)?engineer\b",
    r"\bstaff\s+(?:software\s+)?(?:development\s+)?engineer\b",
    r"\b(?:engineering|technical)\s+program\s+manager\b",
]

# Negative non-technical title patterns to exclude
HIMALAYAS_NEGATIVE_TITLE_PATTERNS = [
    r"\b(?:tax\s+analyst|tax\s+accountant|tax\s+specialist|tax\s+compliance|tax\s+technologist|tax\s+technology)\b",
    r"\b(?:accountant|accounting|finance|payroll|financial|budget)\b",
    r"\b(?:sales|account|business\s+development)\s+(?:executive|manager|representative)\b",
    r"\b(?:recruiter|talent\s+acquisition|sourcer|sourcing\s+recruiter)\b",
    r"\bhuman\s+resources\b",
    r"\b(?:buyer|procurement|purchasing|sourcing\s+manager)\b",
    r"\bcontracts?\s+(?:specialist|manager|administrator)\b",
    r"\b(?:clinical|heor|nurse|medical|health\s+economics)\b",
    r"\blegal\b",
    r"\b(?:sales|pre-sales|solutions?|technical\s+sales)\s+engineer\b",
    r"\b(?:solutions?|implementation|pre-sales|technical)\s+consultant\b",
    r"\bcustomer\s+solutions?\s+(?:architect|arc|consultant)\b",
    r"\b(?:technology\s+operations|it\s+support|technical\s+support|support\s+center|service\s+desk)\s+(?:analyst|manager|specialist)\b",
    r"\bsystems?\s+administrator\b",
    r"\bcloud\s+program\s+manager\b",
]


def is_himalayas_engineering_job(
    title: str | None,
    categories: list | None,
    parent_categories: list | None,
) -> tuple[bool, str]:
    """
    Evaluates whether a Himalayas job listing qualifies as an engineering/technical position.

    Evaluation order:
    1. Normalize title, categories, and parent categories.
    2. Check negative job-family patterns with exemption for bona fide software/architect roles.
    3. Accept if recognized technical title pattern matches.
    4. Accept if recognized technical category metadata is present and title is not generic/operational.
    5. Reject non-technical or insufficiently qualified positions.
    """
    title_clean = (title or "").strip()
    if not title_clean:
        return False, "Missing or empty job title."

    # Normalize category lists safely
    norm_parents: list[str] = []
    if isinstance(parent_categories, list):
        for p in parent_categories:
            if p and isinstance(p, str):
                norm_parents.append(p.strip().lower())

    norm_cats: list[str] = []
    if isinstance(categories, list):
        for c in categories:
            if c and isinstance(c, str):
                norm_cats.append(c.strip().lower())

    has_positive_parent = any(p in HIMALAYAS_POSITIVE_CATEGORIES for p in norm_parents)
    has_positive_category = any(c in HIMALAYAS_POSITIVE_CATEGORY_SLUGS for c in norm_cats)
    has_positive_title = any(
        re.search(pat, title_clean, re.IGNORECASE) for pat in HIMALAYAS_POSITIVE_TITLE_PATTERNS
    )
    has_negative_title = any(
        re.search(pat, title_clean, re.IGNORECASE) for pat in HIMALAYAS_NEGATIVE_TITLE_PATTERNS
    )

    # Context exemption: bona fide software engineering or developer roles in domain-specific platforms
    # (e.g. "Software Engineer - Tax Platform" or "Software Architect - Tax Research" or "Backend Developer - Financial Ledger")
    is_explicit_core_engineer = bool(
        re.search(
            r"\b(?:software\s+(?:engineer|developer|architect)|(?:backend|frontend|full[\s-]?stack)\s+(?:engineer|developer))\b",
            title_clean,
            re.IGNORECASE,
        )
    )

    # 1. Negative title filter takes precedence unless explicitly a core software engineer/developer
    if has_negative_title and not is_explicit_core_engineer:
        return False, f"Title matched negative non-technical pattern: '{title_clean}'"

    # 2. Positive title pattern match qualifies directly
    if has_positive_title:
        return True, "Accepted technical title pattern"

    # 3. Category evidence qualifies only if the title itself is not a generic/operational non-engineering title
    if (has_positive_parent or has_positive_category) and not has_negative_title:
        is_generic_title = bool(
            re.search(
                r"\b(?:analyst|consultant|specialist|manager|director|coordinator|officer|associate|executive|expert|recorder|arc)\b",
                title_clean,
                re.IGNORECASE,
            )
        )
        if not is_generic_title:
            return True, "Accepted technical category with technical title"
        else:
            return False, f"Generic non-engineering title rejected despite category: '{title_clean}'"

    return False, f"Job does not match engineering/technical category or title: '{title_clean}'"


def parse_salary(val) -> Decimal | None:
    """Safely converts numeric or string salary into Decimal."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_himalayas_date(val) -> datetime | None:
    """Parses Himalayas date value (Unix timestamp integer/float or ISO string)."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=dt_timezone.utc)
        except Exception:
            return None
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.isdigit():
            try:
                return datetime.fromtimestamp(int(val_str), tz=dt_timezone.utc)
            except Exception:
                return None
        try:
            return parse_datetime(val_str)
        except Exception:
            return None
    return None


def extract_himalayas_country(location_restrictions: list | None) -> tuple[str, str]:
    """
    Extracts normalized country code and a database-safe human-readable
    location string.

    The complete locationRestrictions list is preserved separately in
    raw_metadata. The returned location is limited to 255 characters
    because ExternalJob.location is a VARCHAR(255).
    """
    max_location_length = 255

    if not location_restrictions:
        return "GLOBAL", "Worldwide (Remote)"

    if isinstance(location_restrictions, str):
        location_restrictions = [location_restrictions]

    cleaned = [str(r).strip() for r in location_restrictions if str(r).strip()]
    if not cleaned:
        return "GLOBAL", "Worldwide (Remote)"

    # Check for United States / US presence
    for r in cleaned:
        if r.lower() in ("united states", "united states of america", "usa", "us"):
            country_code = "US"
            break
    else:
        # Extract primary country code
        first_r = cleaned[0].lower()
        country_code = COUNTRY_NAME_TO_CODE.get(first_r)

        if not country_code:
            if len(cleaned[0]) == 2 and cleaned[0].isalpha():
                country_code = cleaned[0].upper()
            else:
                country_code = cleaned[0][:10].upper()

    suffix = " (Remote)"
    available_length = max_location_length - len(suffix)

    location_parts = []
    current_length = 0

    for country in cleaned:
        separator_length = 2 if location_parts else 0
        proposed_length = current_length + separator_length + len(country)

        if proposed_length > available_length:
            break

        location_parts.append(country)
        current_length = proposed_length

    if location_parts:
        location_str = ", ".join(location_parts) + suffix
    else:
        location_str = cleaned[0][:available_length].rstrip(", ") + suffix

    return country_code, location_str


def get_or_create_himalayas_source() -> ExternalJobSource:
    """Retrieve or initialize the Himalayas ExternalJobSource record."""
    source, _ = ExternalJobSource.objects.get_or_create(
        provider_code=HIMALAYAS_PROVIDER_CODE,
        defaults={
            "name": HIMALAYAS_DISPLAY_NAME,
            "api_enabled": True,
            "attribution_name": HIMALAYAS_DISPLAY_NAME,
            "attribution_url": HIMALAYAS_ATTRIBUTION_URL,
        },
    )
    return source


def sync_himalayas_jobs(
    max_pages: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    query_group: str | None = None,
    queries: list[str] | str | None = None,
    country: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Production-safe synchronization of external public remote jobs from Himalayas Remote Jobs API.
    Consumes https://himalayas.app/jobs/api using cursor-based pagination.
    No authentication key is required.

    Safety:
    - If any page request fails, the entire sync is aborted.
    - Stale job deactivation (reconciliation) ONLY runs after all pages complete successfully.
    """
    start_time = timezone.now()
    source = get_or_create_himalayas_source()
    if not dry_run:
        source.last_sync_status = ExternalJobSource.SyncStatus.RUNNING
        source.save(update_fields=["last_sync_status"])

    pages_fetched = 0
    jobs_received = 0
    jobs_created = 0
    jobs_updated = 0
    jobs_skipped = 0
    jobs_marked_inactive = 0
    validation_errors = 0
    api_errors = 0

    # Resolve queries and mode
    resolved_queries: list[str] = []
    if queries:
        if isinstance(queries, str):
            resolved_queries = [q.strip() for q in queries.split("|") if q.strip()]
        elif isinstance(queries, (list, tuple, set)):
            resolved_queries = [str(q).strip() for q in queries if str(q).strip()]
    elif query_group:
        q_key = query_group.strip().lower()
        if q_key in HIMALAYAS_QUERY_GROUPS:
            resolved_queries = list(HIMALAYAS_QUERY_GROUPS[q_key])
        else:
            logger.warning(f"Unknown query group '{query_group}'; falling back to generic feed.")

    is_targeted_search = bool(resolved_queries)
    target_country = (country or "").strip()

    if is_targeted_search:
        base_api_url = (
            getattr(settings, "HIMALAYAS_SEARCH_API_URL", None)
            or os.getenv("HIMALAYAS_SEARCH_API_URL")
            or HIMALAYAS_SEARCH_API_URL
        )
    else:
        base_api_url = (
            getattr(settings, "HIMALAYAS_API_URL", None)
            or os.getenv("HIMALAYAS_API_URL")
            or HIMALAYAS_BASE_API_URL
        )
    limit = min(max(1, page_size), 20)  # Himalayas supports max 20 per request
    max_p = max_pages if max_pages is not None else getattr(settings, "HIMALAYAS_MAX_PAGES", DEFAULT_MAX_PAGES)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "PeopleRemotely-JobSync/1.0",
            "Accept": "application/json",
        }
    )

    api_key = getattr(settings, "HIMALAYAS_API_KEY", None) or os.getenv("HIMALAYAS_API_KEY")
    if api_key:
        session.headers["Authorization"] = f"Bearer {api_key}"

    successfully_processed_ext_ids: set[str] = set()

    try:
        iteration_queries = resolved_queries if is_targeted_search else [None]

        for current_query in iteration_queries:
            cursor: str | None = None
            query_pages_fetched = 0

            while True:
                params = {"limit": limit}
                if is_targeted_search and current_query:
                    params["q"] = current_query
                if is_targeted_search and target_country:
                    params["country"] = target_country

                if cursor is not None and cursor != "":
                    params["cursor"] = str(cursor)

                try:
                    retry_attempt = 0
                    while True:
                        response = session.get(base_api_url, params=params, timeout=15)
                        if response.status_code == 429:
                            if retry_attempt < MAX_RETRIES_PER_PAGE:
                                wait_time = RETRY_DELAYS[retry_attempt]
                                retry_attempt += 1
                                logger.warning(
                                    f"Himalayas API returned HTTP 429 on page {pages_fetched + 1} "
                                    f"(retry {retry_attempt}/{MAX_RETRIES_PER_PAGE}). Waiting {wait_time}s..."
                                )
                                time.sleep(wait_time)
                                continue
                            else:
                                logger.error(
                                    f"Himalayas API returned HTTP 429 on page {pages_fetched + 1} "
                                    f"after {MAX_RETRIES_PER_PAGE} retries. Aborting sync."
                                )
                        response.raise_for_status()
                        data = response.json()
                        break
                except Exception as req_err:
                    api_errors += 1
                    logger.error(
                        f"Error fetching Himalayas API page {pages_fetched + 1} (query={current_query}, cursor={cursor}): {req_err}"
                    )
                    if not dry_run:
                        source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
                        source.last_sync_error = str(req_err)
                        source.save(update_fields=["last_sync_status", "last_sync_error"])

                    # PARTIAL SYNC SAFETY: Abort sync immediately. Do NOT mark jobs inactive on partial sync failure.
                    return {
                        "provider": HIMALAYAS_PROVIDER_CODE,
                        "success": False,
                        "mode": "targeted_search" if is_targeted_search else "generic_feed",
                        "query_group": query_group,
                        "queries": resolved_queries,
                        "country": target_country,
                        "dry_run": dry_run,
                        "pages_fetched": pages_fetched,
                        "jobs_received": jobs_received,
                        "jobs_created": jobs_created,
                        "jobs_updated": jobs_updated,
                        "jobs_skipped": jobs_skipped,
                        "jobs_marked_inactive": 0,
                        "validation_errors": validation_errors,
                        "api_errors": api_errors,
                        "error": str(req_err),
                        "duration_seconds": (timezone.now() - start_time).total_seconds(),
                    }

                pages_fetched += 1
                query_pages_fetched += 1
                raw_jobs = data.get("jobs", [])
                jobs_received += len(raw_jobs)

                for item in raw_jobs:
                    raw_guid = item.get("guid") or item.get("applicationLink") or item.get("id")
                    if not raw_guid:
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    ext_id = str(raw_guid).strip()
                    successfully_processed_ext_ids.add(ext_id)

                    title = (item.get("title") or "").strip()
                    if not title:
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    company_name = (item.get("companyName") or "Unknown Company").strip()
                    company_slug = (item.get("companySlug") or "").strip()
                    company_website = (
                        f"https://himalayas.app/companies/{company_slug}"
                        if company_slug
                        else None
                    )

                    raw_desc = (
                        item.get("description") or item.get("excerpt") or ""
                    ).strip()
                    description = html_to_plain_text(raw_desc)

                    location_restrictions = item.get("locationRestrictions") or []
                    country_code, location_str = extract_himalayas_country(location_restrictions)

                    remote_type = ExternalJob.RemoteType.REMOTE
                    employment_type = item.get("employmentType")

                    salary_min = parse_salary(item.get("minSalary"))
                    salary_max = parse_salary(item.get("maxSalary"))
                    salary_currency = (item.get("currency") or "USD").strip().upper()

                    categories = item.get("categories") or []
                    parent_categories = item.get("parentCategories") or []

                    # Phase 6R: Engineering-focused category and title filtering
                    is_eng, eng_reason = is_himalayas_engineering_job(
                        title=title,
                        categories=categories,
                        parent_categories=parent_categories,
                    )
                    if not is_eng:
                        logger.info(
                            f"Skipping non-engineering Himalayas listing {ext_id}: {eng_reason}"
                        )
                        jobs_skipped += 1
                        continue

                    all_categories = categories + parent_categories

                    from common.skill_extraction import extract_technical_skills

                    category_skills = extract_technical_skills(all_categories)
                    text_skills = extract_technical_skills(f"{title}\n{description}")
                    tech_stack = sorted(list(set(category_skills) | set(text_skills)))

                    original_job_url = (item.get("applicationLink") or "").strip()
                    if not original_job_url:
                        logger.info(f"Skipping Himalayas job {ext_id}: missing application link.")
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    source_job_url = original_job_url

                    # Posted date & 7-day retention validation
                    pub_date_raw = item.get("pubDate")
                    if pub_date_raw is None or pub_date_raw == "":
                        logger.info(
                            f"Skipping Himalayas listing {ext_id}: missing publication date (pubDate=None)."
                        )
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    posted_at = parse_himalayas_date(pub_date_raw)
                    if not posted_at:
                        logger.info(
                            f"Skipping Himalayas listing {ext_id}: invalid publication date ({pub_date_raw})."
                        )
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    expires_at = parse_himalayas_date(item.get("expiryDate"))

                    # Ingestion retention filter: reject listings older than configurable window (default: 14 days)
                    ingestion_max_days = int(
                        getattr(settings, "HIMALAYAS_INGESTION_MAX_DAYS", None)
                        or os.getenv("HIMALAYAS_INGESTION_MAX_DAYS", DEFAULT_INGESTION_MAX_DAYS)
                    )
                    max_age_cutoff = timezone.now() - timedelta(days=ingestion_max_days)
                    if posted_at < max_age_cutoff:
                        logger.info(
                            f"Skipping stale Himalayas listing {ext_id}: posted_at ({posted_at}) is older than {ingestion_max_days} days."
                        )
                        jobs_skipped += 1
                        continue

                    dedup_hash = generate_dedup_hash(
                        company_name=company_name,
                        title=title,
                        country=country_code,
                        remote_type=remote_type,
                        location=location_str,
                    )

                    raw_metadata = {
                        "company_name": company_name,
                        "company_slug": company_slug,
                        "company_logo": item.get("companyLogo"),
                        "seniority": item.get("seniority"),
                        "location_restrictions": location_restrictions,
                        "timezone_restrictions": item.get("timezoneRestrictions"),
                        "categories": categories,
                        "parent_categories": parent_categories,
                        "salary_period": item.get("salaryPeriod"),
                        "min_salary": item.get("minSalary"),
                        "max_salary": item.get("maxSalary"),
                        "currency": item.get("currency"),
                        "guid": item.get("guid"),
                        "application_link": item.get("applicationLink"),
                        "excerpt": item.get("excerpt"),
                    }

                    defaults = {
                        "title": title,
                        "company_name": company_name,
                        "company_website": company_website,
                        "description": description,
                        "location": location_str,
                        "country": country_code,
                        "remote_type": remote_type,
                        "employment_type": employment_type,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "salary_currency": salary_currency,
                        "tech_stack": tech_stack,
                        "original_job_url": original_job_url,
                        "source_job_url": source_job_url,
                        "source_name": HIMALAYAS_DISPLAY_NAME,
                        "posted_at": posted_at,
                        "expires_at": expires_at,
                        "is_active": True,
                        "status": ExternalJob.Status.ACTIVE,
                        "dedup_hash": dedup_hash,
                        "raw_metadata": raw_metadata,
                    }

                    if not dry_run:
                        try:
                            _, created = ExternalJob.objects.update_or_create(
                                source=source,
                                external_job_id=ext_id,
                                defaults=defaults,
                            )
                            if created:
                                jobs_created += 1
                            else:
                                jobs_updated += 1
                        except Exception as db_err:
                            logger.error(f"Error saving Himalayas job {ext_id}: {db_err}")
                            validation_errors += 1
                            jobs_skipped += 1
                    else:
                        if ExternalJob.objects.filter(source=source, external_job_id=ext_id).exists():
                            jobs_updated += 1
                        else:
                            jobs_created += 1

                # Check next cursor
                next_cursor = data.get("nextCursor")
                if next_cursor is None or next_cursor == "":
                    # No more pages to fetch for this query
                    break

                cursor = next_cursor

                # Safety page limit check if specified
                if max_p is not None and query_pages_fetched >= max_p:
                    break

                # Delay between successful page requests to reduce throttling risk
                time.sleep(INTER_PAGE_DELAY)

            if is_targeted_search and len(iteration_queries) > 1:
                time.sleep(INTER_PAGE_DELAY)

        # Stale Reconciliation:
        # CRITICAL SAFETY: Only execute provider-wide stale reconciliation in generic feed mode.
        # Targeted searches must NOT deactivate unrelated jobs absent from a narrow keyword search.
        if not dry_run and not is_targeted_search:
            stale_queryset = ExternalJob.objects.filter(
                source=source,
                is_active=True,
            ).exclude(external_job_id__in=successfully_processed_ext_ids)

            jobs_marked_inactive = stale_queryset.update(
                is_active=False,
                status=ExternalJob.Status.INACTIVE,
            )

        active_jobs_count = ExternalJob.objects.filter(
            source=source,
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        ).count()

        if not dry_run:
            source.active_jobs_count = active_jobs_count
            source.last_sync_status = ExternalJobSource.SyncStatus.SUCCESS
            source.last_sync_at = timezone.now()
            source.last_sync_error = None
            source.save(
                update_fields=[
                    "active_jobs_count",
                    "last_sync_status",
                    "last_sync_at",
                    "last_sync_error",
                ]
            )

        return {
            "provider": HIMALAYAS_PROVIDER_CODE,
            "success": True,
            "mode": "targeted_search" if is_targeted_search else "generic_feed",
            "query_group": query_group,
            "queries": resolved_queries,
            "country": target_country,
            "dry_run": dry_run,
            "pages_fetched": pages_fetched,
            "jobs_received": jobs_received,
            "jobs_created": jobs_created,
            "jobs_updated": jobs_updated,
            "jobs_skipped": jobs_skipped,
            "jobs_marked_inactive": jobs_marked_inactive,
            "validation_errors": validation_errors,
            "api_errors": api_errors,
            "active_jobs_count": active_jobs_count,
            "duration_seconds": (timezone.now() - start_time).total_seconds(),
        }

    except Exception as unhandled_err:
        logger.exception(f"Unhandled exception in Himalayas sync: {unhandled_err}")
        if not dry_run:
            source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
            source.last_sync_error = str(unhandled_err)
            source.save(update_fields=["last_sync_status", "last_sync_error"])
        return {
            "provider": HIMALAYAS_PROVIDER_CODE,
            "success": False,
            "mode": "targeted_search" if is_targeted_search else "generic_feed",
            "query_group": query_group,
            "queries": resolved_queries,
            "country": target_country,
            "dry_run": dry_run,
            "pages_fetched": pages_fetched,
            "jobs_received": jobs_received,
            "jobs_created": jobs_created,
            "jobs_updated": jobs_updated,
            "jobs_skipped": jobs_skipped,
            "jobs_marked_inactive": 0,
            "validation_errors": validation_errors,
            "api_errors": api_errors,
            "error": str(unhandled_err),
            "duration_seconds": (timezone.now() - start_time).total_seconds(),
        }
