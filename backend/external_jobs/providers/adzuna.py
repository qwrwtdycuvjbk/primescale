import logging
import os
import re
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from external_jobs.models import ExternalJobSource, ExternalJob
from external_jobs.utils import classify_remote_type, generate_dedup_hash

logger = logging.getLogger(__name__)

ADZUNA_PROVIDER_CODE = "adzuna"
ADZUNA_DISPLAY_NAME = "Adzuna"
ADZUNA_ATTRIBUTION_URL = "https://www.adzuna.com"
ADZUNA_BASE_API_URL = "https://api.adzuna.com/v1/api/jobs"

# Default conservative configuration
DEFAULT_COUNTRY = "us"
DEFAULT_SEARCH_WHAT = (
    "software developer|software engineer|python developer|django developer|"
    "react developer|javascript developer|full stack developer|backend developer|frontend developer"
)
DEFAULT_MAX_PAGES = 3
DEFAULT_RESULTS_PER_PAGE = 20


def clean_html(raw_text: str | None) -> str:
    """Strip basic HTML tags often returned in Adzuna snippets."""
    if not raw_text:
        return ""
    return re.sub(r"<[^>]+>", "", raw_text).strip()


def parse_salary(val) -> Decimal | None:
    """Safely convert salary value to Decimal."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_search_queries(what_input: str | list[str] | None) -> list[str]:
    """
    Parses search query string (pipe-separated or single) or sequence into a list of cleaned query strings.
    Ignores empty queries and strips surrounding whitespace.
    """
    if what_input is None or what_input == "":
        raw = getattr(settings, "ADZUNA_SEARCH_WHAT", None) or os.getenv(
            "ADZUNA_SEARCH_WHAT", DEFAULT_SEARCH_WHAT
        )
    else:
        raw = what_input

    if isinstance(raw, (list, tuple, set)):
        queries = [str(q).strip() for q in raw if str(q).strip()]
    elif isinstance(raw, str):
        queries = [q.strip() for q in raw.split("|") if q.strip()]
    else:
        queries = []

    return queries or ["software developer"]


def get_or_create_adzuna_source() -> ExternalJobSource:
    """Retrieve or initialize the Adzuna ExternalJobSource record."""
    source, _ = ExternalJobSource.objects.get_or_create(
        provider_code=ADZUNA_PROVIDER_CODE,
        defaults={
            "name": ADZUNA_DISPLAY_NAME,
            "api_enabled": True,
            "attribution_name": ADZUNA_DISPLAY_NAME,
            "attribution_url": ADZUNA_ATTRIBUTION_URL,
        },
    )
    return source


def sync_adzuna_jobs(
    country: str | None = None,
    what: str | list[str] | None = None,
    location: str | None = None,
    max_pages: int | None = None,
    results_per_page: int | None = None,
) -> dict:
    """
    Production-safe synchronization of external public jobs from the official Adzuna API.
    Supports multi-query synchronization in a single run with unified stale reconciliation.
    Consumes https://api.adzuna.com/v1/api/jobs/{country}/search/{page} via HTTP GET.
    Credentials (app_id, app_key) are securely retrieved from Django settings or environment.
    """
    start_time = timezone.now()
    source = get_or_create_adzuna_source()
    source.last_sync_status = ExternalJobSource.SyncStatus.RUNNING
    source.save(update_fields=["last_sync_status"])

    # Resolve configuration
    country_code = (
        country
        or getattr(settings, "ADZUNA_COUNTRY", None)
        or os.getenv("ADZUNA_COUNTRY", DEFAULT_COUNTRY)
    ).strip().lower()

    queries = parse_search_queries(what)

    max_p = int(
        max_pages
        or getattr(settings, "ADZUNA_MAX_PAGES", None)
        or os.getenv("ADZUNA_MAX_PAGES", DEFAULT_MAX_PAGES)
    )

    rpp = int(
        results_per_page
        or getattr(settings, "ADZUNA_RESULTS_PER_PAGE", None)
        or os.getenv("ADZUNA_RESULTS_PER_PAGE", DEFAULT_RESULTS_PER_PAGE)
    )

    app_id = (
        getattr(settings, "ADZUNA_APP_ID", None)
        or os.getenv("ADZUNA_APP_ID", "")
    ).strip()

    app_key = (
        getattr(settings, "ADZUNA_APP_KEY", None)
        or os.getenv("ADZUNA_APP_KEY", "")
    ).strip()

    total_pages_fetched = 0
    total_jobs_received = 0
    jobs_created = 0
    jobs_updated = 0
    jobs_skipped = 0
    jobs_marked_inactive = 0
    validation_errors = 0
    api_errors = 0
    query_details = []

    # Validate credentials presence without logging secrets
    if not app_id or not app_key:
        err_msg = "Adzuna credentials (ADZUNA_APP_ID / ADZUNA_APP_KEY) are not configured."
        logger.error(err_msg)
        source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
        source.last_sync_error = "Adzuna credentials missing"
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return {
            "provider": ADZUNA_PROVIDER_CODE,
            "success": False,
            "country": country_code,
            "queries": queries,
            "queries_processed": 0,
            "pages_fetched": 0,
            "jobs_received": 0,
            "jobs_created": 0,
            "jobs_updated": 0,
            "jobs_skipped": 0,
            "jobs_marked_inactive": 0,
            "validation_errors": 0,
            "api_errors": 1,
            "query_details": [],
            "error": err_msg,
            "duration_seconds": (timezone.now() - start_time).total_seconds(),
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "PeopleRemotely-JobSync/1.0",
            "Accept": "application/json",
        }
    )

    # Accumulate all seen Adzuna IDs across all search queries
    all_seen_ext_ids: set[str] = set()
    full_sync_successful = False

    try:
        for current_query in queries:
            query_pages_count = 0
            query_received_count = 0

            for page_num in range(1, max_p + 1):
                target_url = f"{ADZUNA_BASE_API_URL}/{country_code}/search/{page_num}"
                params = {
                    "app_id": app_id,
                    "app_key": app_key,
                    "results_per_page": rpp,
                    "what": current_query,
                    "content-type": "application/json",
                }
                if location:
                    params["where"] = location

                try:
                    response = session.get(target_url, params=params, timeout=15)
                    response.raise_for_status()
                    data = response.json()
                except Exception as req_err:
                    api_errors += 1
                    # Safely log error without exposing query parameters that contain app_key
                    logger.error(
                        f"Error fetching Adzuna API query='{current_query}' page={page_num} "
                        f"({ADZUNA_BASE_API_URL}/{country_code}/search/{page_num}): {type(req_err).__name__}"
                    )
                    source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
                    source.last_sync_error = (
                        f"API failure for query '{current_query}' page {page_num}: {type(req_err).__name__}"
                    )
                    source.save(update_fields=["last_sync_status", "last_sync_error"])

                    # PARTIAL SYNC SAFETY: Abort sync immediately. Do NOT mark jobs inactive on partial sync failure.
                    return {
                        "provider": ADZUNA_PROVIDER_CODE,
                        "success": False,
                        "country": country_code,
                        "queries": queries,
                        "queries_processed": len(query_details),
                        "pages_fetched": total_pages_fetched,
                        "jobs_received": total_jobs_received,
                        "jobs_created": jobs_created,
                        "jobs_updated": jobs_updated,
                        "jobs_skipped": jobs_skipped,
                        "jobs_marked_inactive": 0,
                        "validation_errors": validation_errors,
                        "api_errors": api_errors,
                        "query_details": query_details,
                        "error": f"API failure for query '{current_query}' page {page_num}: {type(req_err).__name__}",
                        "duration_seconds": (timezone.now() - start_time).total_seconds(),
                    }

                total_pages_fetched += 1
                query_pages_count += 1
                results = data.get("results", [])
                if not results:
                    # No more jobs available for this query
                    break

                total_jobs_received += len(results)
                query_received_count += len(results)

                for item in results:
                    raw_id = item.get("id")
                    if raw_id is None:
                        validation_errors += 1
                        jobs_skipped += 1
                        continue

                    ext_id = str(raw_id)
                    all_seen_ext_ids.add(ext_id)

                    title = clean_html(item.get("title") or "Position Unspecified")
                    description = clean_html(item.get("description") or "")

                    # Extract company
                    company_obj = item.get("company")
                    if isinstance(company_obj, dict):
                        company_name = (company_obj.get("display_name") or "Company Not Specified").strip()
                    elif company_obj:
                        company_name = str(company_obj).strip()
                    else:
                        company_name = "Company Not Specified"

                    # Extract location details
                    location_obj = item.get("location")
                    location_str = None
                    area = []
                    city = None
                    state = None
                    parsed_country = country_code.upper()

                    if isinstance(location_obj, dict):
                        location_str = (location_obj.get("display_name") or "").strip() or None
                        area = location_obj.get("area") or []
                        if isinstance(area, list) and len(area) > 0:
                            # area list structure typically: ["US", "State", "County", "City"]
                            if len(area) > 1:
                                state = area[1]
                            if len(area) > 2:
                                city = area[-1]
                    elif location_obj:
                        location_str = str(location_obj).strip()

                    # Remote classification using existing utility (checks full title + description)
                    remote_context = f"{title} {description}"
                    remote_type = classify_remote_type(
                        location_str=location_str,
                        raw_remote_str=remote_context,
                    )

                    # Employment / contract type
                    contract_time = item.get("contract_time")
                    contract_type = item.get("contract_type")
                    emp_parts = [p.replace("_", " ").title() for p in [contract_time, contract_type] if p]
                    employment_type = " ".join(emp_parts) if emp_parts else None

                    # Salary
                    salary_min = parse_salary(item.get("salary_min"))
                    salary_max = parse_salary(item.get("salary_max"))
                    salary_currency = "USD" if parsed_country == "US" else "GBP" if parsed_country == "GB" else "EUR" if parsed_country in ("FR", "DE", "IT", "NL") else "USD"

                    # Tech stack & category tags
                    skills = []
                    category_obj = item.get("category")
                    if isinstance(category_obj, dict):
                        cat_label = category_obj.get("label")
                        if cat_label and cat_label not in skills:
                            skills.append(cat_label)

                    # Original redirect URL
                    original_job_url = item.get("redirect_url") or ""

                    # Posted date
                    created_raw = item.get("created")
                    posted_at = None
                    if created_raw:
                        posted_at = parse_datetime(created_raw)
                        if posted_at and timezone.is_naive(posted_at):
                            posted_at = timezone.make_aware(posted_at)

                    dedup_hash = generate_dedup_hash(
                        company_name=company_name,
                        title=title,
                        country=parsed_country,
                        remote_type=remote_type,
                        location=location_str,
                    )

                    defaults = {
                        "title": title,
                        "company_name": company_name,
                        "company_website": None,
                        "description": description,
                        "location": location_str,
                        "country": parsed_country,
                        "state": state,
                        "city": city,
                        "remote_type": remote_type,
                        "employment_type": employment_type,
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "salary_currency": salary_currency,
                        "tech_stack": skills,
                        "original_job_url": original_job_url,
                        "source_name": ADZUNA_DISPLAY_NAME,
                        "posted_at": posted_at,
                        "status": ExternalJob.Status.ACTIVE,
                        "is_active": True,
                        "dedup_hash": dedup_hash,
                        "raw_metadata": item,
                    }

                    obj, created = ExternalJob.objects.update_or_create(
                        source=source,
                        external_job_id=ext_id,
                        defaults=defaults,
                    )

                    if created:
                        jobs_created += 1
                    else:
                        jobs_updated += 1

                # If fewer results than requested were returned, we have reached the end of this query
                if len(results) < rpp:
                    break

            query_details.append(
                {
                    "query": current_query,
                    "pages": query_pages_count,
                    "received": query_received_count,
                }
            )

        full_sync_successful = True

    except Exception as e:
        api_errors += 1
        logger.error(f"Unexpected error in Adzuna multi-query job sync: {type(e).__name__}")
        source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
        source.last_sync_error = str(e)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return {
            "provider": ADZUNA_PROVIDER_CODE,
            "success": False,
            "country": country_code,
            "queries": queries,
            "queries_processed": len(query_details),
            "pages_fetched": total_pages_fetched,
            "jobs_received": total_jobs_received,
            "jobs_created": jobs_created,
            "jobs_updated": jobs_updated,
            "jobs_skipped": jobs_skipped,
            "jobs_marked_inactive": 0,
            "validation_errors": validation_errors,
            "api_errors": api_errors,
            "query_details": query_details,
            "error": str(e),
            "duration_seconds": (timezone.now() - start_time).total_seconds(),
        }

    # PARTIAL SYNC SAFETY: Reconcile stale jobs ONLY after 100% full sync success across ALL queries
    if full_sync_successful:
        stale_jobs = ExternalJob.objects.filter(
            source=source, is_active=True
        ).exclude(external_job_id__in=all_seen_ext_ids)
        jobs_marked_inactive = stale_jobs.update(
            is_active=False, status=ExternalJob.Status.INACTIVE
        )

        source.last_sync_at = timezone.now()
        source.last_sync_status = ExternalJobSource.SyncStatus.SUCCESS
        source.last_sync_error = None
        source.active_jobs_count = ExternalJob.objects.filter(
            source=source, is_active=True, status=ExternalJob.Status.ACTIVE
        ).count()
        source.save(
            update_fields=[
                "last_sync_at",
                "last_sync_status",
                "last_sync_error",
                "active_jobs_count",
            ]
        )

    duration = (timezone.now() - start_time).total_seconds()
    logger.info(
        f"Adzuna Combined Sync Complete: Country={country_code}, Queries={len(queries)}, "
        f"Pages={total_pages_fetched}, Received={total_jobs_received}, Created={jobs_created}, "
        f"Updated={jobs_updated}, Inactive={jobs_marked_inactive}, Duration={duration:.2f}s"
    )

    return {
        "provider": ADZUNA_PROVIDER_CODE,
        "success": True,
        "country": country_code,
        "queries": queries,
        "queries_processed": len(queries),
        "pages_fetched": total_pages_fetched,
        "jobs_received": total_jobs_received,
        "jobs_created": jobs_created,
        "jobs_updated": jobs_updated,
        "jobs_skipped": jobs_skipped,
        "jobs_marked_inactive": jobs_marked_inactive,
        "validation_errors": validation_errors,
        "api_errors": api_errors,
        "query_details": query_details,
        "duration_seconds": duration,
    }
