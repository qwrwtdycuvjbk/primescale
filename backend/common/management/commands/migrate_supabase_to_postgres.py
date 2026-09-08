"""
Django management command: migrate_supabase_to_postgres
Phase 10 — Supabase -> Local PostgreSQL Data Migration

Features:
- Extracts data from Supabase REST / PostgREST (or from a provided JSON export file)
- Enforces strict read-only safety on the source
- Runs full pre-validation (UUID validation, referential integrity check, array transformations, email normalization)
- Supports --dry-run (validates and reports without inserting records)
- Supports local backup before writing to local PostgreSQL
- Executes all database insertions in a single atomic transaction
- Preserves exact source UUIDs across all tables
- Sets unusable passwords on migrated users (triggering welcome/password reset in Phase 11)
- Never triggers side-effects (no emails, no Celery jobs, no matching engine runs)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company, CompanyMember
from handoffs.models import HandoffRequest
from jobs.models import Job
from matching.models import Match

from common.migration_dry_run import (
    MigrationDryRunner,
    transform_availability,
    transform_privacy,
    transform_skills,
    transform_work_type,
    validate_uuid,
)


class Command(BaseCommand):
    help = "Migrates production data from Supabase into the local PostgreSQL database (peopleremotely_local)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform all validations and print report without writing to PostgreSQL.",
        )
        parser.add_argument(
            "--file",
            type=str,
            default=None,
            help="Path to an existing JSON export file containing Supabase tables.",
        )
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Skip creating a local backup before migration.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        file_path = options["file"]
        skip_backup = options["no_backup"]

        self.stdout.write(self.style.NOTICE("=" * 70))
        self.stdout.write(self.style.NOTICE("Phase 10 — Supabase -> Local PostgreSQL Data Migration"))
        self.stdout.write(self.style.NOTICE("=" * 70))

        target_db = settings.DATABASES["default"]["NAME"]
        target_host = settings.DATABASES["default"].get("HOST", "127.0.0.1")
        target_vendor = settings.DATABASES["default"].get("ENGINE", "")

        self.stdout.write(f"Target Database: {target_db} on {target_host} ({target_vendor})")
        if dry_run:
            self.stdout.write(self.style.WARNING("MODE: DRY RUN (No records will be inserted)"))
        else:
            self.stdout.write(self.style.SUCCESS("MODE: EXECUTION (Inserting into local PostgreSQL)"))

        # 1. Fetch / Load source dataset
        data = self._load_data(file_path)

        # 2. Run Dry-Run Validation
        self.stdout.write("\nValidating dataset structure and referential integrity...")
        runner = MigrationDryRunner()
        runner.load_dataset(data)
        summary = runner.get_summary()

        self.stdout.write(f"Source row counts:")
        for table, count in summary["counts"].items():
            self.stdout.write(f"  - {table}: {count}")

        # Check for legacy role_submissions
        raw_submissions = data.get("role_submissions", [])
        if raw_submissions:
            self.stdout.write(
                self.style.WARNING(
                    f"  - role_submissions (legacy): {len(raw_submissions)} records detected (preserved for separate archive)"
                )
            )

        if summary["issues"]:
            self.stdout.write(self.style.ERROR(f"\nFound {len(summary['issues'])} validation errors:"))
            for issue in summary["issues"][:10]:
                self.stdout.write(self.style.ERROR(f"  ! {issue}"))
            if len(summary["issues"]) > 10:
                self.stdout.write(self.style.ERROR(f"  ...and {len(summary['issues']) - 10} more"))
            raise CommandError("Data validation failed. Aborting migration to maintain database integrity.")

        self.stdout.write(self.style.SUCCESS("Validation passed with 0 errors."))

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n[DRY RUN COMPLETE] Dataset is clean and ready for migration."))
            return

        # 3. Create local backup of current tables if not skipped
        if not skip_backup:
            self._create_local_backup()

        # 4. Perform Atomic Database Migration
        self.stdout.write("\nStarting database migration inside atomic transaction...")
        try:
            with transaction.atomic():
                stats = self._execute_migration(data)
            self.stdout.write(self.style.SUCCESS("\nMigration transaction committed successfully!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nMigration failed: {e}. Transaction rolled back."))
            raise

        # 5. Print Final Summary Table
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("MIGRATION COMPLETED SUCCESSFULLY"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"{'Table':<25} | {'Source':<10} | {'Migrated':<10} | {'Status':<10}")
        self.stdout.write("-" * 65)
        for tbl, cnt in stats.items():
            src_cnt = summary["counts"].get(tbl, 0)
            status = "MATCH" if src_cnt == cnt else "DIFF"
            self.stdout.write(f"{tbl:<25} | {src_cnt:<10} | {cnt:<10} | {status:<10}")

    def _load_data(self, file_path: Optional[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Loads data from specified JSON file or Supabase API."""
        if file_path:
            p = Path(file_path)
            if not p.exists():
                raise CommandError(f"Specified data file does not exist: {file_path}")
            self.stdout.write(f"Reading dataset from file: {p.resolve()}")
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)

        # Look for default export file in backend/
        default_export = Path(settings.BASE_DIR) / "supabase_export.json"
        if default_export.exists():
            self.stdout.write(f"Reading dataset from default export: {default_export}")
            with open(default_export, "r", encoding="utf-8") as f:
                return json.load(f)

        # Attempt to read from Supabase REST API if credentials are in env
        supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if supabase_url and supabase_key:
            return self._extract_from_supabase_api(supabase_url, supabase_key)

        # If no credentials, return an empty template with clean empty tables
        self.stdout.write(self.style.NOTICE("No export file or live Supabase credentials provided; using empty dataset."))
        return {
            "profiles": [],
            "companies": [],
            "company_members": [],
            "candidate_profiles": [],
            "jobs": [],
            "matches": [],
            "handoff_requests": [],
            "role_submissions": [],
        }

    def _extract_from_supabase_api(self, url: str, key: str) -> Dict[str, List[Dict[str, Any]]]:
        """Read-only extraction from Supabase PostgREST endpoints."""
        import urllib.request

        self.stdout.write(f"Extracting live data via Supabase PostgREST API: {url} (READ-ONLY)")
        tables = [
            "profiles",
            "companies",
            "company_members",
            "candidate_profiles",
            "jobs",
            "matches",
            "handoff_requests",
            "role_submissions",
        ]
        result: Dict[str, List[Dict[str, Any]]] = {}

        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }

        for table in tables:
            req_url = f"{url.rstrip('/')}/rest/v1/{table}?select=*"
            try:
                req = urllib.request.Request(req_url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        rows = json.loads(resp.read().decode("utf-8"))
                        result[table] = rows
                        self.stdout.write(f"  - Extracted {len(rows)} rows from {table}")
                    else:
                        result[table] = []
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ! Note: Could not extract {table}: {e}"))
                result[table] = []

        return result

    def _create_local_backup(self):
        """Creates a timestamped JSON backup of current local tables."""
        backup_dir = Path(settings.BASE_DIR) / "migration_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"local_db_backup_{ts}.backup.json"

        local_snapshot = {
            "profiles": list(User.objects.values()),
            "companies": list(Company.objects.values()),
            "company_members": list(CompanyMember.objects.values()),
            "candidate_profiles": list(CandidateProfile.objects.values()),
            "jobs": list(Job.objects.values()),
            "matches": list(Match.objects.values()),
            "handoff_requests": list(HandoffRequest.objects.values()),
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(local_snapshot, f, indent=2, default=str)

        self.stdout.write(f"Local backup saved to: {backup_file.name}")

    def _execute_migration(self, data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """Executes idempotent database insertion in strict dependency order."""
        stats = {
            "users": 0,
            "companies": 0,
            "company_members": 0,
            "candidate_profiles": 0,
            "jobs": 0,
            "matches": 0,
            "handoff_requests": 0,
        }

        # 1. Users / Profiles
        for p in data.get("profiles", []):
            uid = validate_uuid(p.get("id"))
            if not uid:
                continue
            email = (p.get("email") or "").strip().lower()
            role = p.get("role", User.Role.CANDIDATE)
            if role not in [User.Role.CANDIDATE, User.Role.EMPLOYER, User.Role.ADMIN]:
                role = User.Role.CANDIDATE

            user, created = User.objects.get_or_create(
                id=uid,
                defaults={
                    "email": email,
                    "full_name": (p.get("full_name") or "").strip(),
                    "phone": p.get("phone"),
                    "role": role,
                    "is_active": True,
                    "is_staff": (role == User.Role.ADMIN),
                    "is_superuser": (role == User.Role.ADMIN),
                },
            )
            if not created and user.email != email:
                user.email = email
                user.full_name = (p.get("full_name") or "").strip()
                user.phone = p.get("phone")
                user.role = role
            user.set_unusable_password()
            user.save(update_fields=["password"])
            stats["users"] += 1


        # 2. Companies
        for c in data.get("companies", []):
            cid = validate_uuid(c.get("id"))
            owner_id = validate_uuid(c.get("owner_id"))
            if not cid or not owner_id:
                continue
            owner = User.objects.filter(id=owner_id).first()
            if not owner:
                continue

            company, created = Company.objects.get_or_create(
                id=cid,
                defaults={
                    "owner": owner,
                    "name": (c.get("name") or "").strip(),
                    "website": c.get("website"),
                    "size": c.get("size"),
                    "country": c.get("country") or "US",
                    "logo_url": c.get("logo_url"),
                    "description": c.get("description"),
                    "hq_city": c.get("hq_city"),
                    "industry": c.get("industry"),
                    "remote_culture_statement": c.get("remote_culture_statement"),
                    "domain_verified": bool(c.get("domain_verified", False)),
                    "badge_remote_first": bool(c.get("badge_remote_first", False)),
                    "badge_visa_sponsor": bool(c.get("badge_visa_sponsor", False)),
                    "badge_gcc": bool(c.get("badge_gcc", False)),
                    "profile_complete": bool(c.get("profile_complete", False)),
                },
            )
            stats["companies"] += 1

        # 3. Company Members
        for m in data.get("company_members", []):
            mid = validate_uuid(m.get("id"))
            cid = validate_uuid(m.get("company_id"))
            uid = validate_uuid(m.get("user_id"))
            if not mid or not cid or not uid:
                continue
            company = Company.objects.filter(id=cid).first()
            user = User.objects.filter(id=uid).first()
            if not company or not user:
                continue

            member_role = m.get("member_role", CompanyMember.MemberRole.ADMIN)
            if member_role not in [
                CompanyMember.MemberRole.ADMIN,
                CompanyMember.MemberRole.RECRUITER,
                CompanyMember.MemberRole.HIRING_MANAGER,
            ]:
                member_role = CompanyMember.MemberRole.ADMIN

            CompanyMember.objects.get_or_create(
                id=mid,
                defaults={
                    "company": company,
                    "user": user,
                    "member_role": member_role,
                },
            )
            stats["company_members"] += 1

        # 4. Candidate Profiles
        for cp in data.get("candidate_profiles", []):
            cpid = validate_uuid(cp.get("id"))
            uid = validate_uuid(cp.get("user_id"))
            if not cpid or not uid:
                continue
            user = User.objects.filter(id=uid).first()
            if not user:
                continue

            CandidateProfile.objects.get_or_create(
                id=cpid,
                defaults={
                    "user": user,
                    "headline": cp.get("headline"),
                    "phone": cp.get("phone"),
                    "current_title": cp.get("current_title"),
                    "years_experience": cp.get("years_experience"),
                    "skills": transform_skills(cp.get("skills")),
                    "role_categories": transform_skills(cp.get("role_categories")),
                    "experience_level": cp.get("experience_level"),
                    "salary_min": cp.get("salary_min"),
                    "salary_max": cp.get("salary_max"),
                    "work_authorization": cp.get("work_authorization"),
                    "us_state": cp.get("us_state"),
                    "remote_preference": cp.get("remote_preference") or "remote",
                    "preferred_work_type": transform_work_type(cp.get("preferred_work_type")),
                    "resume_url": cp.get("resume_url"),
                    "github_url": cp.get("github_url"),
                    "portfolio_url": cp.get("portfolio_url"),
                    "linkedin_url": cp.get("linkedin_url"),
                    "bio": cp.get("bio"),
                    "availability_status": transform_availability(cp.get("availability_status")),
                    "privacy_visibility": transform_privacy(cp.get("privacy_visibility")),
                    "profile_completeness": cp.get("profile_completeness", 0) or 0,
                    "open_to_matching": bool(cp.get("open_to_matching", True)),
                    "profile_complete": bool(cp.get("profile_complete", False)),
                    "source": cp.get("source"),
                },
            )
            stats["candidate_profiles"] += 1

        # 5. Jobs
        for j in data.get("jobs", []):
            jid = validate_uuid(j.get("id"))
            cid = validate_uuid(j.get("company_id"))
            pby = validate_uuid(j.get("posted_by"))
            if not jid or not cid or not pby:
                continue
            company = Company.objects.filter(id=cid).first()
            posted_by = User.objects.filter(id=pby).first()
            if not company or not posted_by:
                continue

            status_val = j.get("status", Job.Status.DRAFT)
            if status_val not in [c[0] for c in Job.Status.choices]:
                status_val = Job.Status.DRAFT

            Job.objects.get_or_create(
                id=jid,
                defaults={
                    "company": company,
                    "posted_by": posted_by,
                    "title": (j.get("title") or "").strip(),
                    "description": (j.get("description") or "").strip(),
                    "role_type": j.get("role_type") or "full-time",
                    "experience_level": j.get("experience_level") or "mid",
                    "tech_stack": transform_skills(j.get("tech_stack")),
                    "salary_range": j.get("salary_range"),
                    "work_type": j.get("work_type") or "remote",
                    "visa_requirements": j.get("visa_requirements"),
                    "status": status_val,
                    "expires_at": j.get("expires_at"),
                    "jd_quality_score": j.get("jd_quality_score"),
                    "jd_quality_feedback": j.get("jd_quality_feedback"),
                    "featured": bool(j.get("featured", False)),
                },
            )
            stats["jobs"] += 1

        # 6. Matches
        for m in data.get("matches", []):
            mid = validate_uuid(m.get("id"))
            cpid = validate_uuid(m.get("candidate_profile_id"))
            jid = validate_uuid(m.get("job_id"))
            if not mid or not cpid or not jid:
                continue
            cp = CandidateProfile.objects.filter(id=cpid).first()
            job = Job.objects.filter(id=jid).first()
            if not cp or not job:
                continue

            status_val = m.get("status", Match.Status.SUGGESTED)
            if status_val not in [c[0] for c in Match.Status.choices]:
                status_val = Match.Status.SUGGESTED

            Match.objects.get_or_create(
                id=mid,
                defaults={
                    "candidate_profile": cp,
                    "job": job,
                    "match_score": m.get("match_score", 0) or 0,
                    "match_reason": m.get("match_reason"),
                    "status": status_val,
                    "visible_to_employer": bool(m.get("visible_to_employer", False)),
                    "recruiter_notified_at": m.get("recruiter_notified_at"),
                },
            )
            stats["matches"] += 1

        # 7. Handoff Requests
        for h in data.get("handoff_requests", []):
            hid = validate_uuid(h.get("id"))
            mid = validate_uuid(h.get("match_id"))
            if not hid or not mid:
                continue
            match = Match.objects.filter(id=mid).first()
            if not match:
                continue

            status_val = h.get("status", HandoffRequest.Status.PENDING)
            if status_val not in [c[0] for c in HandoffRequest.Status.choices]:
                status_val = HandoffRequest.Status.PENDING

            HandoffRequest.objects.get_or_create(
                id=hid,
                defaults={
                    "match": match,
                    "status": status_val,
                    "notes": h.get("notes"),
                    "notified_at": h.get("notified_at"),
                },
            )
            stats["handoff_requests"] += 1

        return stats
