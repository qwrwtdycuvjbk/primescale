"""
Dry-run migration and validation tooling for Supabase -> Django PostgreSQL.
Reads data from Supabase exports/connection, validates referential integrity,
tests data transformations, and produces a validation audit report without
inserting data into Django PostgreSQL.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


def validate_uuid(val: Any) -> Optional[UUID]:
    """Validate that value is a valid UUID."""
    if not val:
        return None
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return None


def transform_skills(val: Any) -> List[str]:
    """
    Transforms Supabase skills (which can be PostgreSQL text[], JSON list, or comma-separated string)
    into a clean list of strings for Django's JSONField.
    """
    if not val:
        return []
    if isinstance(val, list):
        return [str(s).strip() for s in val if str(s).strip()]
    if isinstance(val, str):
        # Handle stringified array or comma-separated
        cleaned = val.strip("{}[] \t\n\r")
        if not cleaned:
            return []
        return [s.strip(" \"'") for s in cleaned.split(",") if s.strip(" \"'")]
    return []


def transform_work_type(val: Optional[str]) -> str:
    """Normalize work type to Django choices."""
    if not val:
        return "remote"
    normalized = val.strip().lower()
    if normalized in ["remote", "hybrid", "onsite"]:
        return normalized
    return "remote"


def transform_availability(val: Optional[str]) -> str:
    """Normalize availability status to Django choices."""
    if not val:
        return "actively_looking"
    normalized = val.strip().lower()
    if normalized in ["actively_looking", "open", "not_looking"]:
        return normalized
    return "actively_looking"


def transform_privacy(val: Optional[str]) -> str:
    """Normalize privacy visibility to Django choices."""
    if not val:
        return "employers_only"
    normalized = val.strip().lower()
    if normalized in ["public", "employers_only", "invite_only"]:
        return normalized
    return "employers_only"


class MigrationDryRunner:
    """
    Validates dataset referential integrity, transforms fields, and checks for
    potential schema violations across Users, Companies, Jobs, CandidateProfiles,
    Matches, and HandoffRequests.
    """

    def __init__(self):
        self.users: Dict[UUID, Dict[str, Any]] = {}
        self.companies: Dict[UUID, Dict[str, Any]] = {}
        self.company_members: List[Dict[str, Any]] = []
        self.candidate_profiles: Dict[UUID, Dict[str, Any]] = {}
        self.jobs: Dict[UUID, Dict[str, Any]] = {}
        self.matches: Dict[UUID, Dict[str, Any]] = {}
        self.handoff_requests: Dict[UUID, Dict[str, Any]] = {}

        self.issues: List[str] = []
        self.warnings: List[str] = []

    def load_dataset(self, data: Dict[str, List[Dict[str, Any]]]):
        """Load records from in-memory dictionary representation of Supabase tables."""
        raw_profiles = data.get("profiles", [])
        raw_companies = data.get("companies", [])
        raw_members = data.get("company_members", [])
        raw_candidates = data.get("candidate_profiles", [])
        raw_jobs = data.get("jobs", [])
        raw_matches = data.get("matches", [])
        raw_handoffs = data.get("handoff_requests", [])

        # 1. Users / Profiles
        for p in raw_profiles:
            uid = validate_uuid(p.get("id"))
            if not uid:
                self.issues.append(f"Profile has invalid UUID: {p.get('id')}")
                continue
            email = (p.get("email") or "").strip().lower()
            if not email:
                self.issues.append(f"Profile {uid} is missing required email.")
                continue
            self.users[uid] = {
                "id": uid,
                "email": email,
                "full_name": p.get("full_name", "").strip(),
                "phone": p.get("phone"),
                "role": p.get("role", "candidate"),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at"),
            }

        # 2. Companies
        for c in raw_companies:
            cid = validate_uuid(c.get("id"))
            owner_id = validate_uuid(c.get("owner_id"))
            if not cid:
                self.issues.append(f"Company has invalid UUID: {c.get('id')}")
                continue
            if not owner_id or owner_id not in self.users:
                self.issues.append(f"Company {cid} has orphaned owner_id {c.get('owner_id')}")
            self.companies[cid] = {
                "id": cid,
                "owner_id": owner_id,
                "name": (c.get("name") or "").strip(),
                "website": c.get("website"),
                "size": c.get("size"),
                "country": c.get("country", "US"),
                "logo_url": c.get("logo_url"),
                "description": c.get("description"),
                "hq_city": c.get("hq_city"),
                "industry": c.get("industry"),
                "remote_culture_statement": c.get("remote_culture_statement"),
                "domain_verified": bool(c.get("domain_verified", False)),
                "profile_complete": bool(c.get("profile_complete", False)),
            }

        # 2.5 Company Members
        for m in raw_members:
            mid = validate_uuid(m.get("id"))
            cid = validate_uuid(m.get("company_id"))
            uid = validate_uuid(m.get("user_id"))
            if not mid:
                self.issues.append(f"CompanyMember has invalid UUID: {m.get('id')}")
                continue
            if not cid or cid not in self.companies:
                self.issues.append(f"CompanyMember {mid} has orphaned company_id {m.get('company_id')}")
            if not uid or uid not in self.users:
                self.issues.append(f"CompanyMember {mid} has orphaned user_id {m.get('user_id')}")
            self.company_members.append(m)

        # 3. Candidate Profiles
        for cp in raw_candidates:
            cpid = validate_uuid(cp.get("id"))
            user_id = validate_uuid(cp.get("user_id"))
            if not cpid:
                self.issues.append(f"CandidateProfile has invalid UUID: {cp.get('id')}")
                continue
            if not user_id or user_id not in self.users:
                self.issues.append(f"CandidateProfile {cpid} has orphaned user_id {cp.get('user_id')}")
            skills = transform_skills(cp.get("skills"))
            role_categories = transform_skills(cp.get("role_categories"))
            self.candidate_profiles[cpid] = {
                "id": cpid,
                "user_id": user_id,
                "headline": cp.get("headline"),
                "skills": skills,
                "role_categories": role_categories,
                "experience_level": cp.get("experience_level"),
                "availability_status": transform_availability(cp.get("availability_status")),
                "preferred_work_type": transform_work_type(cp.get("preferred_work_type")),
                "privacy_visibility": transform_privacy(cp.get("privacy_visibility")),
                "resume_url": cp.get("resume_url"),
            }

        # 4. Jobs
        for j in raw_jobs:
            jid = validate_uuid(j.get("id"))
            company_id = validate_uuid(j.get("company_id"))
            posted_by = validate_uuid(j.get("posted_by"))
            if not jid:
                self.issues.append(f"Job has invalid UUID: {j.get('id')}")
                continue
            if not company_id or company_id not in self.companies:
                self.issues.append(f"Job {jid} has orphaned company_id {j.get('company_id')}")
            if not posted_by or posted_by not in self.users:
                self.issues.append(f"Job {jid} has orphaned posted_by {j.get('posted_by')}")
            self.jobs[jid] = {
                "id": jid,
                "company_id": company_id,
                "posted_by": posted_by,
                "title": (j.get("title") or "").strip(),
                "tech_stack": transform_skills(j.get("tech_stack")),
                "salary_range": j.get("salary_range"),
                "status": j.get("status", "draft"),
            }

        # 5. Matches
        for m in raw_matches:
            mid = validate_uuid(m.get("id"))
            cpid = validate_uuid(m.get("candidate_profile_id"))
            jid = validate_uuid(m.get("job_id"))
            if not mid:
                self.issues.append(f"Match has invalid UUID: {m.get('id')}")
                continue
            if not cpid or cpid not in self.candidate_profiles:
                self.issues.append(f"Match {mid} has orphaned candidate_profile_id {m.get('candidate_profile_id')}")
            if not jid or jid not in self.jobs:
                self.issues.append(f"Match {mid} has orphaned job_id {m.get('job_id')}")
            self.matches[mid] = {
                "id": mid,
                "candidate_profile_id": cpid,
                "job_id": jid,
                "match_score": m.get("match_score", 0),
                "status": m.get("status", "suggested"),
            }

        # 6. Handoff Requests
        for h in raw_handoffs:
            hid = validate_uuid(h.get("id"))
            mid = validate_uuid(h.get("match_id"))
            if not hid:
                self.issues.append(f"HandoffRequest has invalid UUID: {h.get('id')}")
                continue
            if not mid or mid not in self.matches:
                self.issues.append(f"HandoffRequest {hid} has orphaned match_id {h.get('match_id')}")
            self.handoff_requests[hid] = {
                "id": hid,
                "match_id": mid,
                "status": h.get("status", "pending"),
            }

    def get_summary(self) -> Dict[str, Any]:
        """Return dry-run verification summary."""
        return {
            "counts": {
                "users": len(self.users),
                "companies": len(self.companies),
                "company_members": len(self.company_members),
                "candidate_profiles": len(self.candidate_profiles),
                "jobs": len(self.jobs),
                "matches": len(self.matches),
                "handoff_requests": len(self.handoff_requests),
            },
            "issues_count": len(self.issues),
            "issues": self.issues,
            "status": "PASS" if len(self.issues) == 0 else "FAIL",
        }

