import logging
import requests
from django.utils import timezone
from external_jobs.models import ExternalJobSource, ExternalJob
from external_jobs.utils import classify_remote_type, generate_dedup_hash

logger = logging.getLogger(__name__)

PEOPLE_PRIME_PROVIDER_CODE = "people_prime"
PEOPLE_PRIME_DISPLAY_NAME = "People Prime"
PEOPLE_PRIME_API_URL = "https://ats.people-prime.com/api/public/jobs/"
PEOPLE_PRIME_ATTRIBUTION_URL = "https://ats.people-prime.com"

# Country classifier keywords
INDIAN_LOCATION_KEYWORDS = {
    "india", "pan india", "hyderabad", "bengaluru", "bangalore", "mumbai",
    "pune", "delhi", "noida", "gurgaon", "gurugram", "chennai", "kolkata",
    "telangana", "karnataka", "maharashtra", "tamil nadu", "haryana", "andhra"
}

US_LOCATION_KEYWORDS = {
    "us", "usa", "united states", "america", "tx", "ca", "ny", "wa", "fl", "il",
    "austin", "new york", "san francisco", "chicago", "seattle", "boston"
}


def extract_country(city: str | None, state: str | None, location: str | None) -> str:
    combined = f"{city or ''} {state or ''} {location or ''}".lower()
    for kw in INDIAN_LOCATION_KEYWORDS:
        if kw in combined:
            return "IN"
    for kw in US_LOCATION_KEYWORDS:
        if kw in combined:
            return "US"
    return "UNKNOWN"


def get_or_create_people_prime_source() -> ExternalJobSource:
    source, _ = ExternalJobSource.objects.get_or_create(
        provider_code=PEOPLE_PRIME_PROVIDER_CODE,
        defaults={
            "name": PEOPLE_PRIME_DISPLAY_NAME,
            "api_enabled": True,
            "attribution_name": PEOPLE_PRIME_DISPLAY_NAME,
            "attribution_url": PEOPLE_PRIME_ATTRIBUTION_URL,
        },
    )
    return source


def sync_people_prime_jobs():
    """
    Production-safe synchronization of external public jobs from People Prime ATS API.
    Consumes https://ats.people-prime.com/api/public/jobs/ via HTTP GET (server-side only).
    """
    start_time = timezone.now()
    source = get_or_create_people_prime_source()
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

    next_url = PEOPLE_PRIME_API_URL
    session = requests.Session()
    session.headers.update({"User-Agent": "PeopleRemotely-JobSync/1.0"})

    successfully_processed_ext_ids: set[str] = set()
    full_sync_successful = False

    try:
        while next_url:
            try:
                response = session.get(next_url, timeout=15)
                response.raise_for_status()
                data = response.json()
            except Exception as req_err:
                api_errors += 1
                logger.error(f"Error fetching People Prime API page {next_url}: {req_err}")
                source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
                source.last_sync_error = str(req_err)
                source.save(update_fields=["last_sync_status", "last_sync_error"])
                # PARTIAL SYNC SAFETY: Abort sync immediately. Do NOT mark jobs inactive on partial sync failure.
                return {
                    "provider": PEOPLE_PRIME_PROVIDER_CODE,
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
            results = data.get("results", [])
            jobs_received += len(results)

            for item in results:
                raw_id = item.get("id")
                if raw_id is None:
                    validation_errors += 1
                    jobs_skipped += 1
                    continue

                ext_id = str(raw_id)
                successfully_processed_ext_ids.add(ext_id)

                title = (item.get("position") or "Position Unspecified").strip()
                description = (item.get("description") or "").strip()
                city = item.get("city")
                state = item.get("state")
                location = item.get("location")

                # Combine location string
                loc_parts = [p.strip() for p in [city, state, location] if p and p.strip()]
                location_str = ", ".join(loc_parts) if loc_parts else None

                work_mode = item.get("work_mode")
                remote_type = classify_remote_type(location_str=location_str, raw_remote_str=work_mode)

                country = extract_country(city, state, location)
                employment_type = item.get("job_type")

                # Parse skills and technology
                skills = item.get("required_skills") or []
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",") if s.strip()]
                tech_raw = item.get("technology")
                if tech_raw and isinstance(tech_raw, str):
                    for t in tech_raw.split(","):
                        t_clean = t.strip()
                        if t_clean and t_clean not in skills:
                            skills.append(t_clean)

                original_job_url = f"https://people-prime.com/job-details?id={ext_id}"
                posted_at = item.get("published_at") or item.get("created_at")

                dedup_hash = generate_dedup_hash(
                    company_name="People Prime",
                    title=title,
                    country=country,
                    remote_type=remote_type,
                    location=location_str,
                )

                defaults = {
                    "title": title,
                    "company_name": "People Prime",
                    "company_website": "https://people-prime.com",
                    "description": description,
                    "location": location_str,
                    "country": country,
                    "state": state,
                    "city": city,
                    "remote_type": remote_type,
                    "employment_type": employment_type,
                    "tech_stack": skills,
                    "original_job_url": original_job_url,
                    "source_name": PEOPLE_PRIME_DISPLAY_NAME,
                    "posted_at": posted_at,
                    "status": ExternalJob.Status.ACTIVE,
                    "is_active": True,
                    "dedup_hash": dedup_hash,
                    "raw_metadata": item,
                }

                # Deduplicate by content hash first so identical role postings with different IDs don't duplicate
                existing_dedup = ExternalJob.objects.filter(
                    source=source,
                    dedup_hash=dedup_hash,
                ).first()

                if existing_dedup:
                    for key, val in defaults.items():
                        setattr(existing_dedup, key, val)
                    existing_dedup.save()
                    jobs_updated += 1
                else:
                    obj, created = ExternalJob.objects.update_or_create(
                        source=source,
                        external_job_id=ext_id,
                        defaults=defaults,
                    )
                    if created:
                        jobs_created += 1
                    else:
                        jobs_updated += 1

            next_url = data.get("next")

        full_sync_successful = True

    except Exception as e:
        api_errors += 1
        logger.error(f"Unexpected error in People Prime job sync: {e}")
        source.last_sync_status = ExternalJobSource.SyncStatus.FAILURE
        source.last_sync_error = str(e)
        source.save(update_fields=["last_sync_status", "last_sync_error"])
        return {
            "provider": PEOPLE_PRIME_PROVIDER_CODE,
            "success": False,
            "pages_fetched": pages_fetched,
            "jobs_received": jobs_received,
            "jobs_created": jobs_created,
            "jobs_updated": jobs_updated,
            "jobs_skipped": jobs_skipped,
            "jobs_marked_inactive": 0,
            "validation_errors": validation_errors,
            "api_errors": api_errors,
            "error": str(e),
            "duration_seconds": (timezone.now() - start_time).total_seconds(),
        }

    # PARTIAL SYNC SAFETY: Reconcile stale jobs ONLY after 100% full sync success
    if full_sync_successful:
        stale_jobs = ExternalJob.objects.filter(
            source=source, is_active=True
        ).exclude(external_job_id__in=successfully_processed_ext_ids)
        jobs_marked_inactive = stale_jobs.update(
            is_active=False, status=ExternalJob.Status.INACTIVE
        )

        source.last_sync_at = timezone.now()
        source.last_sync_status = ExternalJobSource.SyncStatus.SUCCESS
        source.last_sync_error = None
        source.active_jobs_count = ExternalJob.objects.filter(
            source=source, is_active=True, status=ExternalJob.Status.ACTIVE
        ).count()
        source.save(update_fields=["last_sync_at", "last_sync_status", "last_sync_error", "active_jobs_count"])

    duration = (timezone.now() - start_time).total_seconds()
    logger.info(
        f"People Prime Sync Complete: Pages={pages_fetched}, Received={jobs_received}, "
        f"Created={jobs_created}, Updated={jobs_updated}, Inactive={jobs_marked_inactive}, "
        f"Duration={duration:.2f}s"
    )

    return {
        "provider": PEOPLE_PRIME_PROVIDER_CODE,
        "success": True,
        "pages_fetched": pages_fetched,
        "jobs_received": jobs_received,
        "jobs_created": jobs_created,
        "jobs_updated": jobs_updated,
        "jobs_skipped": jobs_skipped,
        "jobs_marked_inactive": jobs_marked_inactive,
        "validation_errors": validation_errors,
        "api_errors": api_errors,
        "duration_seconds": duration,
    }
