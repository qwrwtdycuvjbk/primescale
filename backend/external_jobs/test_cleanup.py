import io
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model

from external_jobs.models import ExternalJob, ExternalJobSource
from external_jobs.cleanup import (
    DEFAULT_RETENTION_DAYS,
    cleanup_external_jobs,
    ALLOWED_CLEANUP_PROVIDERS,
    PROTECTED_PROVIDERS,
)
from external_jobs.tasks import cleanup_external_jobs_task
from external_jobs.providers.adzuna import sync_adzuna_jobs, ADZUNA_PROVIDER_CODE
from external_jobs.providers.himalayas import sync_himalayas_jobs, HIMALAYAS_PROVIDER_CODE
from jobs.models import Job
from companies.models import Company

User = get_user_model()


class ExternalJobCleanupTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

        # Set up ExternalJobSource records
        self.adzuna_source, _ = ExternalJobSource.objects.get_or_create(
            provider_code="adzuna",
            defaults={"name": "Adzuna", "api_enabled": True, "active_jobs_count": 0},
        )
        self.himalayas_source, _ = ExternalJobSource.objects.get_or_create(
            provider_code="himalayas",
            defaults={"name": "Himalayas", "api_enabled": True, "active_jobs_count": 0},
        )
        self.people_prime_source, _ = ExternalJobSource.objects.get_or_create(
            provider_code="people_prime",
            defaults={"name": "People Prime", "api_enabled": True, "active_jobs_count": 0},
        )

        # Set up first-party employer and company for Job model isolation testing
        self.employer_user = User.objects.create_user(
            email="employer_test@example.com",
            password="testpassword123",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="Acme Corp",
            owner=self.employer_user,
        )

    # -------------------------------------------------------------------------
    # Preserved Original Tests from HEAD
    # -------------------------------------------------------------------------

    def test_jobs_aged_20_days_are_preserved(self):
        """Jobs originally posted 20 days ago (within retention window) must be preserved."""
        job_adzuna_20d = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_20d",
            title="Fresh Adzuna Role",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=20),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(days=21, execute=True)

        self.assertEqual(res["eligible_count"], 0)
        self.assertEqual(res["deleted_count"], 0)
        self.assertEqual(res["skipped_fresh"], 1)
        self.assertTrue(ExternalJob.objects.filter(id=job_adzuna_20d.id).exists())

    def test_adzuna_and_himalayas_jobs_aged_22_days_qualify_and_delete(self):
        """Adzuna and Himalayas listings posted 22 days ago qualify and are deleted when execute=True."""
        old_adzuna = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_22d",
            title="Old Adzuna Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=22),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        old_himalayas = ExternalJob.objects.create(
            source=self.himalayas_source,
            external_job_id="himalayas_22d",
            title="Old Himalayas Job",
            company_name="Himalayas Co",
            posted_at=self.now - timedelta(days=25),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(days=21, execute=True)

        self.assertEqual(res["eligible_count"], 2)
        self.assertEqual(res["deleted_count"], 2)
        self.assertFalse(ExternalJob.objects.filter(id=old_adzuna.id).exists())
        self.assertFalse(ExternalJob.objects.filter(id=old_himalayas.id).exists())

    def test_people_prime_ats_jobs_are_never_deleted(self):
        """People Prime ATS jobs must NEVER qualify for deletion even if aged 60+ days."""
        pp_job = ExternalJob.objects.create(
            source=self.people_prime_source,
            external_job_id="pp_90d",
            title="Internal Staff Role",
            company_name="People Prime",
            posted_at=self.now - timedelta(days=90),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        # Even if someone attempts to pass people_prime in providers argument
        res = cleanup_external_jobs(
            days=21,
            execute=True,
            providers=["people_prime", "adzuna"],
        )

        # people_prime is stripped by sanitized_providers
        self.assertNotIn("people_prime", res["target_providers"])
        self.assertEqual(res["eligible_count"], 0)
        self.assertEqual(res["deleted_count"], 0)
        self.assertTrue(ExternalJob.objects.filter(id=pp_job.id).exists())

    def test_employer_created_jobs_remain_untouched(self):
        """First-party employer jobs in jobs.Job model must remain completely untouched."""
        internal_job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Internal Lead Engineer",
            description="First party job description",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.ACTIVE,
        )

        # Create an old external job to trigger deletion
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_delete_me",
            title="Old Adzuna Job",
            company_name="Other Co",
            posted_at=self.now - timedelta(days=40),
        )

        res = cleanup_external_jobs(days=21, execute=True)

        self.assertEqual(res["deleted_count"], 1)
        self.assertTrue(Job.objects.filter(id=internal_job.id).exists())
        self.assertEqual(Job.objects.count(), 1)

    def test_missing_or_invalid_publication_dates_handled_conservatively(self):
        """Listings with posted_at=None must be skipped conservatively and reported, never deleted."""
        missing_date_job = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_no_date",
            title="Job With No Date",
            company_name="Unknown Co",
            posted_at=None,
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(days=21, execute=True)

        self.assertEqual(res["skipped_missing_date"], 1)
        self.assertEqual(res["eligible_count"], 0)
        self.assertEqual(res["deleted_count"], 0)
        self.assertTrue(ExternalJob.objects.filter(id=missing_date_job.id).exists())

    def test_dry_run_performs_zero_data_changing_queries(self):
        """Dry-run (execute=False) must identify eligible jobs without performing deletions."""
        old_job = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_dry_run_test",
            title="Old Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=35),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(days=21, execute=False)

        self.assertTrue(res["dry_run"])
        self.assertEqual(res["eligible_count"], 1)
        self.assertEqual(res["deleted_count"], 0)
        self.assertTrue(ExternalJob.objects.filter(id=old_job.id).exists())

    def test_deletion_requires_explicit_execute_flag(self):
        """Calling cleanup without execute=True leaves all records intact."""
        old_himalayas = ExternalJob.objects.create(
            source=self.himalayas_source,
            external_job_id="him_execute_flag_test",
            title="Old Remote Job",
            company_name="Him Co",
            posted_at=self.now - timedelta(days=28),
        )

        res = cleanup_external_jobs(days=21)  # default execute is False

        self.assertTrue(res["dry_run"])
        self.assertEqual(res["deleted_count"], 0)
        self.assertTrue(ExternalJob.objects.filter(id=old_himalayas.id).exists())

    def test_batched_processing_and_counter_reconciliation(self):
        """Batching deletes records in configured chunk sizes and reconciles active_jobs_count."""
        # Create 5 old jobs and 2 fresh jobs for Adzuna
        for i in range(5):
            ExternalJob.objects.create(
                source=self.adzuna_source,
                external_job_id=f"adzuna_batch_{i}",
                title=f"Old Adzuna Job {i}",
                company_name="Adzuna Co",
                posted_at=self.now - timedelta(days=25 + i),
                is_active=True,
                status=ExternalJob.Status.ACTIVE,
            )
        for i in range(2):
            ExternalJob.objects.create(
                source=self.adzuna_source,
                external_job_id=f"adzuna_fresh_{i}",
                title=f"Fresh Adzuna Job {i}",
                company_name="Adzuna Co",
                posted_at=self.now - timedelta(days=5),
                is_active=True,
                status=ExternalJob.Status.ACTIVE,
            )

        self.adzuna_source.active_jobs_count = 7
        self.adzuna_source.save()

        # Run with batch_size=2
        res = cleanup_external_jobs(days=21, batch_size=2, execute=True)

        self.assertEqual(res["eligible_count"], 5)
        self.assertEqual(res["deleted_count"], 5)
        self.assertEqual(res["batches_processed"], 3)  # 2 + 2 + 1 = 3 batches
        self.assertEqual(ExternalJob.objects.filter(source=self.adzuna_source).count(), 2)

        # Verify active_jobs_count reconciliation
        self.adzuna_source.refresh_from_db()
        self.assertEqual(self.adzuna_source.active_jobs_count, 2)

    def test_age_buckets_breakdown(self):
        """Eligible jobs are correctly partitioned into 21-30, 31-60, and 60+ days buckets."""
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="age_25",
            title="Job 25d",
            company_name="Co",
            posted_at=self.now - timedelta(days=25),
        )
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="age_45",
            title="Job 45d",
            company_name="Co",
            posted_at=self.now - timedelta(days=45),
        )
        ExternalJob.objects.create(
            source=self.himalayas_source,
            external_job_id="age_75",
            title="Job 75d",
            company_name="Co",
            posted_at=self.now - timedelta(days=75),
        )

        res = cleanup_external_jobs(days=21, execute=False)

        buckets = res["eligible_by_age_bucket"]
        self.assertEqual(buckets["21_to_30_days"], 1)
        self.assertEqual(buckets["31_to_60_days"], 1)
        self.assertEqual(buckets["60_plus_days"], 1)

    def test_management_command_dry_run_and_execute_output(self):
        """Management command correctly parses flags and reports diagnostics."""
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="cmd_test_job",
            title="Old Job for Command",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=30),
        )

        # 1. Default dry-run with explicit days=21
        out = io.StringIO()
        call_command("cleanup_external_jobs", days=21, stdout=out)
        output_str = out.getvalue()
        self.assertIn("DRY-RUN (AUDIT ONLY)", output_str)
        self.assertIn("Eligible for deletion:    1", output_str)
        self.assertIn("DRY-RUN COMPLETE: Zero database modifications were performed.", output_str)
        self.assertEqual(ExternalJob.objects.filter(external_job_id="cmd_test_job").count(), 1)

        # 2. Execution mode with explicit days=21
        out_exec = io.StringIO()
        call_command("cleanup_external_jobs", days=21, execute=True, stdout=out_exec)
        exec_str = out_exec.getvalue()
        self.assertIn("EXECUTE (DELETION)", exec_str)
        self.assertIn("Successfully DELETED:     1 jobs", exec_str)
        self.assertEqual(ExternalJob.objects.filter(external_job_id="cmd_test_job").count(), 0)

    def test_celery_task_execution(self):
        """Celery task executes cleanup with configured parameters."""
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="celery_task_job",
            title="Celery Test Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=30),
        )

        res = cleanup_external_jobs_task(days=21, execute=True)

        self.assertEqual(res["deleted_count"], 1)
        self.assertFalse(res["dry_run"])
        self.assertFalse(ExternalJob.objects.filter(external_job_id="celery_task_job").exists())

    # -------------------------------------------------------------------------
    # Step 2: Focused 7-Day Retention Tests
    # -------------------------------------------------------------------------

    def test_default_retention_days_constant_and_cutoff(self):
        """DEFAULT_RETENTION_DAYS must equal 7, and cleanup_external_jobs defaults to 7 days."""
        self.assertEqual(DEFAULT_RETENTION_DAYS, 7)
        res = cleanup_external_jobs()
        self.assertEqual(res["days"], 7)
        self.assertTrue(res["dry_run"])

    def test_jobs_posted_8_days_ago_eligible_and_6_days_ago_preserved(self):
        """Under default 7-day retention, 8-day-old jobs qualify and 6-day-old jobs are preserved."""
        job_8d = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_8d_test",
            title="Old Adzuna Job (8d)",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=8),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        job_6d = ExternalJob.objects.create(
            source=self.himalayas_source,
            external_job_id="himalayas_6d_test",
            title="Fresh Himalayas Job (6d)",
            company_name="Himalayas Co",
            posted_at=self.now - timedelta(days=6),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(execute=False)

        self.assertEqual(res["eligible_count"], 1)
        self.assertEqual(res["skipped_fresh"], 1)
        self.assertTrue(ExternalJob.objects.filter(id=job_8d.id).exists())
        self.assertTrue(ExternalJob.objects.filter(id=job_6d.id).exists())

    def test_jobs_posted_exactly_7_days_ago_not_eligible_strict_inequality(self):
        """Jobs posted exactly at the cutoff (7 days ago) are not eligible under strict '< cutoff_date'."""
        ref_time = self.now
        with patch("django.utils.timezone.now", return_value=ref_time):
            # Exactly 7 days old: posted_at == cutoff_date
            job_exact_7d = ExternalJob.objects.create(
                source=self.adzuna_source,
                external_job_id="adzuna_exact_7d",
                title="Exact 7-day Job",
                company_name="Adzuna Co",
                posted_at=ref_time - timedelta(days=7),
                is_active=True,
                status=ExternalJob.Status.ACTIVE,
            )
            # 7 days plus 1 second old: strictly < cutoff_date
            job_over_7d = ExternalJob.objects.create(
                source=self.adzuna_source,
                external_job_id="adzuna_over_7d",
                title="Over 7-day Job",
                company_name="Adzuna Co",
                posted_at=ref_time - timedelta(days=7, seconds=1),
                is_active=True,
                status=ExternalJob.Status.ACTIVE,
            )

            res = cleanup_external_jobs(execute=False)

            self.assertEqual(res["eligible_count"], 1)
            self.assertEqual(res["skipped_fresh"], 1)
            self.assertTrue(ExternalJob.objects.filter(id=job_exact_7d.id).exists())
            self.assertTrue(ExternalJob.objects.filter(id=job_over_7d.id).exists())

    def test_old_created_at_or_fetched_at_never_used_as_fallback_publication_date(self):
        """Listings with posted_at=None but 30-day-old created_at or fetched_at are never deleted."""
        job_old_meta = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_no_posted_old_meta",
            title="Missing posted_at but old meta",
            company_name="Adzuna Co",
            posted_at=None,
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        ExternalJob.objects.filter(id=job_old_meta.id).update(
            created_at=self.now - timedelta(days=30),
            fetched_at=self.now - timedelta(days=30),
        )

        res = cleanup_external_jobs(execute=True)

        self.assertEqual(res["skipped_missing_date"], 1)
        self.assertEqual(res["eligible_count"], 0)
        self.assertEqual(res["deleted_count"], 0)
        self.assertTrue(ExternalJob.objects.filter(id=job_old_meta.id).exists())

    def test_execute_mode_deletes_only_eligible_external_jobs(self):
        """Execute mode with default 7 days deletes eligible stale listings while leaving others intact."""
        # 1. Eligible old Adzuna job (9 days old)
        old_adzuna = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_old_9d",
            title="Old Adzuna Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=9),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 2. Fresh Adzuna job (3 days old)
        fresh_adzuna = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_fresh_3d",
            title="Fresh Adzuna Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=3),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 3. Missing date job
        no_date_job = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_no_date_exec",
            title="No Date Job",
            company_name="Adzuna Co",
            posted_at=None,
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        # 4. People Prime job (30 days old)
        pp_job = ExternalJob.objects.create(
            source=self.people_prime_source,
            external_job_id="pp_old_30d",
            title="PP Protected Job",
            company_name="People Prime",
            posted_at=self.now - timedelta(days=30),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(execute=True)

        self.assertFalse(res["dry_run"])
        self.assertEqual(res["eligible_count"], 1)
        self.assertEqual(res["deleted_count"], 1)
        self.assertEqual(res["skipped_fresh"], 1)
        self.assertEqual(res["skipped_missing_date"], 1)

        self.assertFalse(ExternalJob.objects.filter(id=old_adzuna.id).exists())
        self.assertTrue(ExternalJob.objects.filter(id=fresh_adzuna.id).exists())
        self.assertTrue(ExternalJob.objects.filter(id=no_date_job.id).exists())
        self.assertTrue(ExternalJob.objects.filter(id=pp_job.id).exists())

    def test_explicit_days_14_override_still_works(self):
        """Explicitly passing days=14 overrides the 7-day default."""
        job_10d = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_10d_override",
            title="10-Day Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=10),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        job_16d = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="adzuna_16d_override",
            title="16-Day Job",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=16),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs(days=14, execute=False)

        self.assertEqual(res["days"], 14)
        self.assertEqual(res["eligible_count"], 1)
        self.assertEqual(res["skipped_fresh"], 1)

    def test_celery_task_default_uses_7_day_retention(self):
        """Celery cleanup task without an explicit days argument defaults to 7 days."""
        old_job = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="celery_default_old_8d",
            title="Celery Old Job (8d)",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=8),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )
        fresh_job = ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="celery_default_fresh_4d",
            title="Celery Fresh Job (4d)",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=4),
            is_active=True,
            status=ExternalJob.Status.ACTIVE,
        )

        res = cleanup_external_jobs_task(execute=True)

        self.assertEqual(res["days"], 7)
        self.assertFalse(res["dry_run"])
        self.assertEqual(res["deleted_count"], 1)
        self.assertFalse(ExternalJob.objects.filter(id=old_job.id).exists())
        self.assertTrue(ExternalJob.objects.filter(id=fresh_job.id).exists())

    def test_management_command_default_uses_7_days_and_requires_execute(self):
        """Management command without --days uses 7 days and requires --execute to delete records."""
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="cmd_default_test_job_9d",
            title="Old Job for Default Command (9d)",
            company_name="Adzuna Co",
            posted_at=self.now - timedelta(days=9),
        )

        # 1. Default invocation (dry-run without passing --days)
        out_dry = io.StringIO()
        call_command("cleanup_external_jobs", stdout=out_dry)
        dry_str = out_dry.getvalue()
        self.assertIn("DRY-RUN (AUDIT ONLY)", dry_str)
        self.assertIn("Retention Cutoff: > 7 days old (posted_at)", dry_str)
        self.assertIn("Eligible for deletion:    1", dry_str)
        self.assertIn("DRY-RUN COMPLETE: Zero database modifications were performed.", dry_str)
        self.assertEqual(
            ExternalJob.objects.filter(external_job_id="cmd_default_test_job_9d").count(), 1
        )

        # 2. Execution mode without passing --days (uses 7-day default)
        out_exec = io.StringIO()
        call_command("cleanup_external_jobs", execute=True, stdout=out_exec)
        exec_str = out_exec.getvalue()
        self.assertIn("EXECUTE (DELETION)", exec_str)
        self.assertIn("Retention Cutoff: > 7 days old (posted_at)", exec_str)
        self.assertIn("Successfully DELETED:     1 jobs", exec_str)
        self.assertEqual(
            ExternalJob.objects.filter(external_job_id="cmd_default_test_job_9d").count(), 0
        )

    def test_age_buckets_breakdown_with_7_day_default(self):
        """Eligible jobs are partitioned into 7-30, 31-60, and 60+ days buckets under 7-day default."""
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="age_15",
            title="Job 15d",
            company_name="Co",
            posted_at=self.now - timedelta(days=15),
        )
        ExternalJob.objects.create(
            source=self.adzuna_source,
            external_job_id="age_45",
            title="Job 45d",
            company_name="Co",
            posted_at=self.now - timedelta(days=45),
        )
        ExternalJob.objects.create(
            source=self.himalayas_source,
            external_job_id="age_75",
            title="Job 75d",
            company_name="Co",
            posted_at=self.now - timedelta(days=75),
        )

        res = cleanup_external_jobs(execute=False)

        buckets = res["eligible_by_age_bucket"]
        self.assertEqual(buckets["7_to_30_days"], 1)
        self.assertEqual(buckets["31_to_60_days"], 1)
        self.assertEqual(buckets["60_plus_days"], 1)


class ProviderIngestionFilterTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.adzuna_source, _ = ExternalJobSource.objects.get_or_create(
            provider_code="adzuna",
            defaults={"name": "Adzuna", "api_enabled": True},
        )
        self.himalayas_source, _ = ExternalJobSource.objects.get_or_create(
            provider_code="himalayas",
            defaults={"name": "Himalayas", "api_enabled": True},
        )

    @override_settings(
        ADZUNA_APP_ID="test-app-id",
        ADZUNA_APP_KEY="test-app-key",
    )
    @patch("external_jobs.providers.adzuna.requests.Session")
    def test_adzuna_skips_listings_older_than_21_days_during_sync(self, mock_session_cls):
        """Adzuna ingestion skips jobs with created > 21 days old and does not insert them."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "fresh_adzuna_1",
                    "title": "Fresh Python Role",
                    "created": (self.now - timedelta(days=5)).isoformat(),
                    "company": {"display_name": "Modern Co"},
                    "description": "Great role",
                    "redirect_url": "https://example.com/adzuna/fresh",
                },
                {
                    "id": "stale_adzuna_1",
                    "title": "Stale 30-Day Role",
                    "created": (self.now - timedelta(days=30)).isoformat(),
                    "company": {"display_name": "Old Co"},
                    "description": "Old role",
                    "redirect_url": "https://example.com/adzuna/stale",
                },
            ]
        }
        mock_session.get.return_value = mock_response

        res = sync_adzuna_jobs(
            country="us",
            what="python",
            max_pages=1,
            results_per_page=10,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_created"], 1)
        self.assertEqual(res["jobs_skipped"], 1)

        # Confirm fresh job was created
        self.assertTrue(ExternalJob.objects.filter(external_job_id="fresh_adzuna_1").exists())
        # Confirm stale job was NOT created
        self.assertFalse(ExternalJob.objects.filter(external_job_id="stale_adzuna_1").exists())

    @patch("external_jobs.providers.himalayas.requests.Session")
    def test_himalayas_skips_listings_older_than_21_days_during_sync(self, mock_session_cls):
        """Himalayas ingestion skips jobs with pubDate > 21 days old and does not insert them."""
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "guid": "fresh_him_1",
                    "title": "Fresh Remote Engineer",
                    "pubDate": (self.now - timedelta(days=3)).isoformat(),
                    "companyName": "Remote Corp",
                    "description": "Fresh description",
                    "applicationLink": "https://example.com/him/fresh",
                },
                {
                    "guid": "stale_him_1",
                    "title": "Stale Remote Engineer",
                    "pubDate": (self.now - timedelta(days=40)).isoformat(),
                    "companyName": "Remote Corp",
                    "description": "Stale description",
                    "applicationLink": "https://example.com/him/stale",
                },
            ],
            "nextCursor": None,
        }
        mock_session.get.return_value = mock_response

        res = sync_himalayas_jobs(max_pages=1)

        self.assertTrue(res["success"])
        self.assertEqual(res["jobs_created"], 1)
        self.assertEqual(res["jobs_skipped"], 1)

        # Confirm fresh job was created
        self.assertTrue(ExternalJob.objects.filter(external_job_id="fresh_him_1").exists())
        # Confirm stale job was NOT created
        self.assertFalse(ExternalJob.objects.filter(external_job_id="stale_him_1").exists())
