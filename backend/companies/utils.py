from urllib.parse import urlparse
from typing import Optional


def extract_email_domain(email: str) -> Optional[str]:
    if not email or "@" not in email:
        return None
    parts = email.split("@")
    if len(parts) != 2:
        return None
    return parts[1].strip().lower()


def extract_website_domain(website: str) -> Optional[str]:
    if not website or not website.strip():
        return None
    try:
        url = website.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host if host else None
    except Exception:
        return None


def is_work_email_domain_verified(work_email: str, website: Optional[str]) -> bool:
    if not website or not website.strip():
        return False
    email_domain = extract_email_domain(work_email)
    site_domain = extract_website_domain(website)
    if not email_domain or not site_domain:
        return False
    return email_domain == site_domain or email_domain.endswith(f".{site_domain}")


def is_company_profile_complete(data: dict) -> bool:
    name = (data.get("name") or "").strip()
    size = data.get("size")
    description = (data.get("description") or "").strip()
    hq_city = (data.get("hq_city") or "").strip()
    industry = (data.get("industry") or "").strip()
    return bool(name and size and description and hq_city and industry)
