import logging
import os
import re
from decimal import Decimal, InvalidOperation
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from external_jobs.models import ExternalJobSource, ExternalJob
from external_jobs.utils import generate_dedup_hash, clean_html_text

logger = logging.getLogger(__name__)

HIMALAYAS_PROVIDER_CODE = "himalayas"
HIMALAYAS_DISPLAY_NAME = "Himalayas"
HIMALAYAS_BASE_API_URL = "https://himalayas.app/jobs/api"
HIMALAYAS_ATTRIBUTION_URL = "https://himalayas.app"
DEFAULT_PAGE_SIZE = 20
DEFAULT_MAX_PAGES = None  # None = fetch all pages until nextCursor is absent

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


def parse_salary(val) -> Decimal | None:
    """Safely converts numeric or string salary into Decimal."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_himalayas_date(val) -> timezone.datetime | None:
    """Parses Himalayas date value (Unix timestamp integer/float or ISO string)."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        try:
            return timezone.datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            return None
    if isinstance(val, str):
        val_str = val.strip()
        if val_str.isdigit():
            try:
                return timezone.datetime.fromtimestamp(int(val_str), tz=timezone.utc)
            except Exception:
                return None
        try:
            return parse_datetime(val_str)
        except Exception:
            return None
    return None


def extract_himalayas_country(location_restrictions: list | None) -> tuple[str, str]:
    """
    Extracts normalized country code and human-readable location string.
    locationRestrictions = [] -> ('GLOBAL', 'Worldwide (Remote)')
    locationRestrictions = ['United States'] -> ('US', 'United States (Remote)')
    locationRestrictions = ['India'] -> ('IN', 'India (Remote)')
    """
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
            return "US", f"{', '.join(cleaned)} (Remote)"

    # Extract primary country code
    first_r = cleaned[0].lower()
    country_code = COUNTRY_NAME_TO_CODE.get(first_r)
    if not country_code:
        if len(cleaned[0]) == 2 and cleaned[0].isalpha():
            country_code = cleaned[0].upper()
        else:
            country_code = cleaned[0][:10].upper()

    return country_code, f"{', '.join(cleaned)} (Remote)"


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

    base_api_url = getattr(settings, "HIMALAYAS_API_URL", None) or HIMALAYAS_BASE_API_URL
    limit = min(max(1, page_size), 20)  # Himalayas supports max 20 per request
    max_p = max_pages if max_pages is not None else getattr(settings, "HIMALAYAS_MAX_PAGES", DEFAULT_MAX_PAGES)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "PeopleRemotely-JobSync/1.0",
            "Accept": "application/json",
        }
    )

    cursor: str | None = None
    successfully_processed_ext_ids: set[str] = set()

    try:
        while True:
            # Construct request URL with limit and cursor
            params = {"limit": limit}
            if cursor is not None and cursor != "":
                params["cursor"] = str(cursor)

            try:
                response = session.get(base_api_url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
            except Exception as req_err:
                api_errors += 1
                logger.error(
                    f"Error fetching Himalayas API page {pages_fetched + 1} (cursor={cursor}): {req_err}"
                )
                source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
                source.last_sync_error = str(req_err)
                source.save(update_fields=["last_sync_status", "last_sync_error"])

                # PARTIAL SYNC SAFETY: Abort sync immediately. Do NOT mark jobs inactive on partial sync failure.
                return {
                    "provider": HIMALAYAS_PROVIDER_CODE,
                    "success": False,
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
                description = clean_html_text(raw_desc)

                location_restrictions = item.get("locationRestrictions") or []
                country, location_str = extract_himalayas_country(location_restrictions)

                remote_type = ExternalJob.RemoteType.REMOTE
                employment_type = item.get("employmentType")

                salary_min = parse_salary(item.get("minSalary"))
                salary_max = parse_salary(item.get("maxSalary"))
                salary_currency = (item.get("currency") or "USD").strip().upper()

                categories = item.get("categories") or []
                parent_categories = item.get("parentCategories") or []
                all_categories = categories + parent_categories
                tech_stack = list(
                    dict.fromkeys(
                        [str(c).strip() for c in all_categories if str(c).strip()]
                    )
                )

                original_job_url = item.get("applicationLink") or ext_id
                source_job_url = item.get("applicationLink") or ext_id

                posted_at = parse_himalayas_date(item.get("pubDate"))
                expires_at = parse_himalayas_date(item.get("expiryDate"))

                dedup_hash = generate_dedup_hash(
                    company_name=company_name,
                    title=title,
                    country=country,
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
                    "country": country,
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

            # Check next cursor
            next_cursor = data.get("nextCursor")
            if next_cursor is None or next_cursor == "":
                # No more pages to fetch
                break

            cursor = next_cursor

            # Safety page limit check if specified
            if max_p is not None and pages_fetched >= max_p:
                break

        # Stale Reconciliation: Deactivate previously active Himalayas jobs not in this successful sync
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
        source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
        source.last_sync_error = str(unhandled_err)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return {
            "provider": HIMALAYAS_PROVIDER_CODE,
            "success": False,
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
