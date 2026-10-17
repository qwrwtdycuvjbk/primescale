"""
Unit and Integration Tests for Job Description Normalization and Embedding Generation (Phase 6).

Strict Safety:
- All NVIDIA API interactions are mocked. Zero live external API calls.
- Runs exclusively on isolated test database.
- Verifies deterministic normalization, eligibility enforcement (excluding external jobs),
  dimension validation, non-finite vector rejection, content-hash idempotency,
  stale overwrite concurrency prevention, and Celery tasks.
"""

import math
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from companies.models import Company
from external_jobs.models import ExternalJob, ExternalJobSource
from common.embedding_client import (
    MAX_INPUT_CHARACTERS,
    EmbeddingAuthenticationError,
    EmbeddingDimensionError,
    EmbeddingPermanentError,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingTransientError,
    EmbeddingValidationError,
    NvidiaEmbeddingClient,
)
from common.resume_extraction import calculate_content_hash
from jobs.models import Job
from matching.job_embeddings import (
    JobEmbeddingResult,
    JobEmbeddingService,
    JobTextPreparationService,
    PreparedJobText,
    get_eligible_job_embeddings,
    invalidate_job_embedding,
    is_eligible_first_party_job,
)
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    EmbeddingStatus,
    JobEmbedding,
)
from matching.tasks import MAX_TASK_RETRY_DELAY, generate_job_embedding_task


def make_dummy_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS, fill: float = 0.05) -> list[float]:
    """Generates a dummy float vector of specified dimension."""
    return [fill] * dim


class JobEligibilityTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_test@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Test",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Acme Remote Corp",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Distributed Systems Engineer",
            description="Build ultra-scalable systems with Python, Django, and PostgreSQL.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            work_type="remote",
            status=Job.Status.ACTIVE,
        )

        self.external_source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
            attribution_name="Adzuna Remote",
        )
        self.external_job = ExternalJob.objects.create(
            source=self.external_source,
            external_job_id="adzuna-101",
            title="Scraped Adzuna Python Engineer",
            company_name="External Co",
            description="External scraped description",
            original_job_url="https://example.com/adzuna/101",
            source_name="Adzuna",
            status=ExternalJob.Status.ACTIVE,
        )

    def test_first_party_active_job_is_eligible(self):
        """Standard active first-party employer job is eligible."""
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertTrue(is_eligible)
        self.assertIsNone(reason)

    def test_external_job_is_explicitly_ineligible(self):
        """ExternalJob instances (Adzuna, Himalayas, People Prime ATS, etc.) are strictly ineligible."""
        is_eligible, reason = is_eligible_first_party_job(self.external_job)
        self.assertFalse(is_eligible)
        self.assertIn("not an instance of first-party Job model", reason)

    def test_non_active_job_statuses_ineligible(self):
        """Jobs in draft, paused, closed, or archived status are ineligible."""
        for inactive_status in (
            Job.Status.DRAFT,
            Job.Status.PAUSED,
            Job.Status.CLOSED,
            Job.Status.ARCHIVED,
        ):
            self.job.status = inactive_status
            is_eligible, reason = is_eligible_first_party_job(self.job)
            self.assertFalse(is_eligible, f"Status {inactive_status} should be ineligible")
            self.assertIn(inactive_status, reason)

    def test_expired_job_is_ineligible(self):
        """Jobs with past expires_at are ineligible."""
        self.job.expires_at = timezone.now() - timedelta(days=1)
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertFalse(is_eligible)
        self.assertIn("expired", reason.lower())

    def test_job_missing_company_or_posted_by_ineligible(self):
        """Jobs lacking company or posted_by relationships are ineligible."""
        self.job.company_id = None
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertFalse(is_eligible)
        self.assertIn("Company", reason)

        self.job.company = self.company
        self.job.posted_by_id = None
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertFalse(is_eligible)
        self.assertIn("User", reason)

    def test_empty_title_or_description_ineligible(self):
        """Jobs with blank or whitespace-only title or description are ineligible."""
        self.job.title = "   "
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertFalse(is_eligible)
        self.assertIn("title is empty", reason)

        self.job.title = "Valid Title"
        self.job.description = "\t\n  "
        is_eligible, reason = is_eligible_first_party_job(self.job)
        self.assertFalse(is_eligible)
        self.assertIn("description is empty", reason)

    def test_write_time_invalidation_when_job_paused(self):
        """When an active job with a completed embedding is paused, write-time signal immediately invalidates embedding."""
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            embedding=make_dummy_vector(),
            status=EmbeddingStatus.COMPLETED,
            embedded_at=timezone.now(),
            version="gen_active",
        )

        self.job.status = Job.Status.PAUSED
        self.job.save(update_fields=["status"])

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)
        self.assertIsNone(job_emb.embedded_at)
        self.assertNotEqual(job_emb.version, "gen_active")

    def test_write_time_invalidation_when_job_content_changed(self):
        """When job content changes such that content hash changes, completed embedding is invalidated to PENDING."""
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            embedding=make_dummy_vector(),
            status=EmbeddingStatus.COMPLETED,
            content_hash="old_hash_12345",
            embedded_at=timezone.now(),
            version="gen_old",
        )

        self.job.title = "Completely Redesigned Distributed Systems Architect"
        self.job.save(update_fields=["title"])

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.PENDING)
        self.assertIsNone(job_emb.embedding)
        self.assertIsNone(job_emb.embedded_at)
        self.assertNotEqual(job_emb.version, "gen_old")

    def test_read_time_filtering_excludes_ineligible_jobs(self):
        """get_eligible_job_embeddings excludes paused, expired, or non-completed jobs."""
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            embedding=make_dummy_vector(),
            status=EmbeddingStatus.COMPLETED,
            embedded_at=timezone.now(),
        )

        # 1. Active eligible job is present
        eligible_ids = list(get_eligible_job_embeddings().values_list("id", flat=True))
        self.assertIn(job_emb.id, eligible_ids)

        # 2. Paused job is excluded
        self.job.status = Job.Status.PAUSED
        self.job.save()
        eligible_ids = list(get_eligible_job_embeddings().values_list("id", flat=True))
        self.assertNotIn(job_emb.id, eligible_ids)

        # 3. Expired job is excluded
        self.job.status = Job.Status.ACTIVE
        self.job.expires_at = timezone.now() - timedelta(minutes=10)
        self.job.save()
        eligible_ids = list(get_eligible_job_embeddings().values_list("id", flat=True))
        self.assertNotIn(job_emb.id, eligible_ids)

    def test_explicit_invalidate_job_embedding_helper(self):
        """invalidate_job_embedding explicitly clears vector, advances generation, and marks FAILED."""
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            embedding=make_dummy_vector(),
            status=EmbeddingStatus.COMPLETED,
            version="v_initial",
        )

        success = invalidate_job_embedding(self.job, reason="Manual admin purge")
        self.assertTrue(success)

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)
        self.assertIn("Manual admin purge", job_emb.error_message)
        self.assertNotEqual(job_emb.version, "v_initial")



class JobTextPreparationServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_prep@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Prep",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Global Prime Tech",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Backend Engineer \u2014 Cloud Infrastructure",
            description=(
                "We are looking for a Senior Backend Engineer.\r\n\r\n"
                "Responsibilities include:\r\n"
                "- Designing distributed APIs\r\n"
                "- Managing PostgreSQL databases\r\n\r\n"
                "Qualifications:\r\n"
                "- 5+ years with Python & Django\r\n"
            ),
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            work_type="remote",
            tech_stack=["Python", "postgresql", "Django", "AWS", "Python"],
            visa_requirements="Must be authorized to work in the US.",
            salary_range="$140,000 - $180,000",
            jd_quality_score=95,
            jd_quality_feedback="Excellent clarity and requirements.",
            featured=True,
            status=Job.Status.ACTIVE,
        )

    def test_deterministic_normalization_and_stable_order(self):
        """Normalizes job text into a deterministic, stably ordered document."""
        prepared = JobTextPreparationService.prepare_text(self.job)

        self.assertTrue(prepared.is_eligible)
        text = prepared.text

        # Verify exact section ordering:
        # Title -> Company -> Role Type -> Experience Level -> Work Type -> Required Skills -> Visa Requirements -> Description
        title_idx = text.find("Job Title:")
        company_idx = text.find("Company:")
        role_idx = text.find("Role Type:")
        exp_idx = text.find("Experience Level:")
        work_idx = text.find("Work Type:")
        skills_idx = text.find("Required Skills:")
        visa_idx = text.find("Visa Requirements:")
        desc_idx = text.find("Job Description:")

        self.assertTrue(0 <= title_idx < company_idx < role_idx < exp_idx < work_idx < skills_idx < visa_idx < desc_idx)

        # Verify sorted and deduplicated skills: AWS, Django, postgresql, Python
        self.assertIn("Required Skills: AWS, Django, postgresql, Python", text)

        # Verify normalized line endings (no CRLF \r\n)
        self.assertNotIn("\r", text)

        # Content hash must be 64-character SHA-256
        self.assertEqual(len(prepared.content_hash), 64)
        self.assertEqual(prepared.content_hash, calculate_content_hash(text))

    def test_strict_exclusion_of_private_and_internal_metadata(self):
        """Strictly excludes pay rates, quality scores/feedback, featured flag, and user credentials."""
        prepared = JobTextPreparationService.prepare_text(self.job)
        text = prepared.text

        # Excluded fields
        self.assertNotIn("140,000", text)
        self.assertNotIn("180,000", text)
        self.assertNotIn("salary", text.lower())
        self.assertNotIn("quality", text.lower())
        self.assertNotIn("feedback", text.lower())
        self.assertNotIn("featured", text.lower())
        self.assertNotIn(self.employer_user.email, text)
        self.assertNotIn(str(self.job.id), text)

    def test_content_hash_changes_when_relevant_content_changes(self):
        """Content hash changes when relevant fields update, and stays unchanged when irrelevant fields update."""
        prep1 = JobTextPreparationService.prepare_text(self.job)

        # Irrelevant field updates (salary, quality score, featured) do NOT change hash
        self.job.salary_range = "$200,000 - $250,000"
        self.job.jd_quality_score = 100
        self.job.featured = False
        prep2 = JobTextPreparationService.prepare_text(self.job)
        self.assertEqual(prep1.content_hash, prep2.content_hash)

        # Relevant field updates (skills, title, description) DO change hash
        self.job.tech_stack = ["Python", "Go", "Kubernetes"]
        prep3 = JobTextPreparationService.prepare_text(self.job)
        self.assertNotEqual(prep1.content_hash, prep3.content_hash)

    def test_missing_optional_fields_handled_cleanly(self):
        """Missing optional fields (visa requirements, tech_stack, company) do not crash or leave empty labels."""
        self.job.visa_requirements = ""
        self.job.tech_stack = []
        self.job.role_type = ""
        prepared = JobTextPreparationService.prepare_text(self.job)

        self.assertTrue(prepared.is_eligible)
        self.assertNotIn("Visa Requirements:", prepared.text)
        self.assertNotIn("Required Skills:", prepared.text)
        self.assertNotIn("Role Type:", prepared.text)
        self.assertIn("Job Title:", prepared.text)
        self.assertIn("Job Description:", prepared.text)

    def test_text_length_capped_at_max_input_characters(self):
        """Huge job descriptions are strictly capped at MAX_INPUT_CHARACTERS (16,000 chars)."""
        huge_desc = "Building planetary scale software systems. " * 600  # ~25,800 chars
        self.job.description = huge_desc
        prepared = JobTextPreparationService.prepare_text(self.job)

        self.assertTrue(prepared.is_eligible)
        self.assertLessEqual(len(prepared.text), MAX_INPUT_CHARACTERS)
        self.assertEqual(len(prepared.text), MAX_INPUT_CHARACTERS)
        self.assertEqual(prepared.character_count, MAX_INPUT_CHARACTERS)


class JobEmbeddingServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_embed@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Embedding Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Prime AI Corp",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior AI Platform Engineer",
            description="Deploy and optimize large language models and vector search on Kubernetes.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            work_type="remote",
            tech_stack=["Python", "PyTorch", "pgvector", "Docker"],
            status=Job.Status.ACTIVE,
        )

        self.mock_client = MagicMock(spec=NvidiaEmbeddingClient)
        self.mock_client.model = TARGET_EMBEDDING_MODEL
        self.service = JobEmbeddingService(client=self.mock_client)

    def test_successful_job_embedding_generation_and_persistence(self):
        """Generates a 2,048-dim vector for eligible job and persists it with complete metadata."""
        dummy_vector = make_dummy_vector()
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_success)
        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(result.dimensions, TARGET_EMBEDDING_DIMENSIONS)
        self.assertEqual(result.model_name, TARGET_EMBEDDING_MODEL)
        self.assertFalse(result.is_unchanged)
        self.assertFalse(result.is_stale)

        # Verify DB record
        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(job_emb.dimensions, TARGET_EMBEDDING_DIMENSIONS)
        self.assertEqual(job_emb.model_name, TARGET_EMBEDDING_MODEL)
        self.assertEqual(list(job_emb.embedding), dummy_vector)
        self.assertEqual(job_emb.content_hash, result.content_hash)
        self.assertIsNotNone(job_emb.embedded_at)
        self.assertGreater(job_emb.text_length, 0)
        self.assertIsNone(job_emb.error_message)

        # Verify client called with passage input_type
        self.mock_client.embed.assert_called_once()
        _, kwargs = self.mock_client.embed.call_args
        self.assertEqual(kwargs["input_type"], "passage")

    def test_unchanged_content_hash_skips_redundant_api_call(self):
        """Skips API call if embedding is already completed with identical content hash."""
        dummy_vector = make_dummy_vector()
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        # Initial call
        res1 = self.service.generate_embedding_for_job(self.job)
        self.assertTrue(res1.is_success)
        self.assertFalse(res1.is_unchanged)
        self.assertEqual(self.mock_client.embed.call_count, 1)

        # Second call with unchanged job content
        res2 = self.service.generate_embedding_for_job(self.job)
        self.assertTrue(res2.is_success)
        self.assertTrue(res2.is_unchanged)
        # Client embed should NOT be called again
        self.assertEqual(self.mock_client.embed.call_count, 1)

    def test_force_regenerate_bypasses_unchanged_check(self):
        """Force regenerate flag re-runs embedding even if content hash matches."""
        dummy_vector = make_dummy_vector()
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        self.service.generate_embedding_for_job(self.job)
        self.assertEqual(self.mock_client.embed.call_count, 1)

        res2 = self.service.generate_embedding_for_job(self.job, force_regenerate=True)
        self.assertTrue(res2.is_success)
        self.assertFalse(res2.is_unchanged)
        self.assertEqual(self.mock_client.embed.call_count, 2)

    def test_ineligible_job_marks_failed_and_clears_embedding(self):
        """Ineligible job (e.g. paused/draft) aborts without calling API and clears existing vectors."""
        # Setup existing completed embedding
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            embedding=make_dummy_vector(),
            status=EmbeddingStatus.COMPLETED,
            embedded_at=timezone.now(),
        )

        # Job is paused
        self.job.status = Job.Status.PAUSED
        self.job.save(update_fields=["status"])

        result = self.service.generate_embedding_for_job(self.job)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("paused", result.error_message.lower())
        self.mock_client.embed.assert_not_called()

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)
        self.assertIsNone(job_emb.embedded_at)

    def test_dimension_validation_failure_marks_failed(self):
        """Returned vector with incorrect dimensions (1024 != 2048) marks record FAILED."""
        bad_vector = make_dummy_vector(dim=1024)
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=bad_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=1024,
        )

        result = self.service.generate_embedding_for_job(self.job)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("dimensions", result.error_message.lower())

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)

    def test_non_finite_vector_values_rejected(self):
        """Vector containing NaN or Inf is rejected and marks record FAILED."""
        bad_vector = make_dummy_vector()
        bad_vector[10] = float("nan")
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=bad_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        result = self.service.generate_embedding_for_job(self.job)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("non-finite", result.error_message.lower())

    def test_concurrent_job_content_edit_discards_stale_vector(self):
        """If job description changes concurrently while API call is in flight, stale vector is discarded."""
        def simulate_concurrent_edit(*args, **kwargs):
            # Concurrent process updates the job title and description
            Job.objects.filter(id=self.job.id).update(
                title="Lead Staff AI Infrastructure Architect",
                description="Updated concurrent job description text.",
            )
            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.1),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_concurrent_edit

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message.lower())

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertIsNone(job_emb.embedding)
        self.assertNotEqual(job_emb.status, EmbeddingStatus.COMPLETED)

    def test_concurrent_job_ineligibility_discards_stale_vector(self):
        """If job is paused or closed while API call is in flight, stale vector is discarded."""
        def simulate_concurrent_pause(*args, **kwargs):
            Job.objects.filter(id=self.job.id).update(status=Job.Status.PAUSED)
            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.1),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_concurrent_pause

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_stale)
        self.assertEqual(result.status, EmbeddingStatus.FAILED)

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertIsNone(job_emb.embedding)

    def test_permanent_authentication_error_marks_failed_without_retry(self):
        """Permanent auth error marks record FAILED immediately."""
        self.mock_client.embed.side_effect = EmbeddingAuthenticationError("Invalid API key")

        result = self.service.generate_embedding_for_job(self.job)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("EmbeddingAuthenticationError", result.error_message)

    def test_transient_error_reraises_when_raise_on_transient_is_true(self):
        """Transient error re-raises when raise_on_transient=True so Celery can handle retries."""
        self.mock_client.embed.side_effect = EmbeddingTransientError("Connection timeout")

        with self.assertRaises(EmbeddingTransientError):
            self.service.generate_embedding_for_job(self.job, raise_on_transient=True)

    def test_job_content_changing_and_returning_to_earlier_hash_aba_problem(self):
        """
        ABA Concurrency Problem:
        Job has text A (hash A). Task 1 starts.
        While Task 1 is calling embed:
        Job is edited to text B, then edited back to text A (job.updated_at changes).
        Task 1 completes and attempts to commit.
        Task 1 must detect that the job was updated concurrently and discard the stale vector.
        """
        initial_hash = calculate_content_hash(self.job.description)

        def simulate_aba_content_edit(*args, **kwargs):
            # Edit 1: change description to B
            self.job.description = "Intermediate Description B"
            self.job.save(update_fields=["description", "updated_at"])

            # Edit 2: change description back to A
            self.job.description = "Deploy and optimize large language models and vector search on Kubernetes."
            self.job.save(update_fields=["description", "updated_at"])

            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.55),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_aba_content_edit

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message.lower())

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertIsNone(job_emb.embedding)
        self.assertNotEqual(job_emb.status, EmbeddingStatus.COMPLETED)

    def test_stale_task_finishing_after_newer_task_does_not_overwrite(self):
        """
        Task 1 starts for Job. While Task 1 is calling API, Task 2 runs and finishes.
        When Task 1 finishes, it detects the version/generation change and discards its vector.
        Task 2's completed embedding is NOT overwritten.
        """
        v2_vector = make_dummy_vector(fill=0.99)

        def simulate_newer_task_completion(*args, **kwargs):
            # Task 2 finishes and saves a new completed embedding
            job_emb = JobEmbedding.objects.get(job=self.job)
            job_emb.embedding = v2_vector
            job_emb.status = EmbeddingStatus.COMPLETED
            job_emb.embedded_at = timezone.now()
            job_emb.version = "generation_task_2"
            job_emb.save()

            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.11),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_newer_task_completion

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_stale)

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(list(job_emb.embedding), v2_vector)
        self.assertEqual(job_emb.version, "generation_task_2")

    def test_stale_task_error_does_not_mark_newer_successful_embedding_as_failed(self):
        """
        Task 1 encounters an error during slow API call.
        Meanwhile, Task 2 completed successfully.
        Task 1's error must NOT overwrite the completed embedding or mark status FAILED.
        """
        v2_vector = make_dummy_vector(fill=0.88)

        def simulate_task_2_success_before_error(*args, **kwargs):
            job_emb = JobEmbedding.objects.get(job=self.job)
            job_emb.embedding = v2_vector
            job_emb.status = EmbeddingStatus.COMPLETED
            job_emb.embedded_at = timezone.now()
            job_emb.version = "generation_newer_success"
            job_emb.save()

            # Task 1 fails with permanent error
            raise EmbeddingPermanentError("HTTP 400 Bad Request on old generation")

        self.mock_client.embed.side_effect = simulate_task_2_success_before_error

        result = self.service.generate_embedding_for_job(self.job)

        # Stale error must be discarded
        self.assertTrue(result.is_stale)

        # DB must still retain the successful embedding from Task 2
        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(list(job_emb.embedding), v2_vector)
        self.assertEqual(job_emb.version, "generation_newer_success")

    def test_duplicate_concurrent_tasks_idempotent(self):
        """
        Two identical tasks start simultaneously. Task A commits first; Task B discards duplicate.
        """
        def simulate_concurrent_duplicate(*args, **kwargs):
            job_emb = JobEmbedding.objects.get(job=self.job)
            job_emb.embedding = make_dummy_vector(fill=0.33)
            job_emb.status = EmbeddingStatus.COMPLETED
            job_emb.version = "gen_task_a"
            job_emb.embedded_at = timezone.now()
            job_emb.save()

            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.33),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_concurrent_duplicate

        result = self.service.generate_embedding_for_job(self.job)

        self.assertTrue(result.is_stale)
        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.version, "gen_task_a")

    def test_input_too_long_handled_as_permanent_failure(self):
        """HTTP 422 Input Too Long / Token Limit Exceeded fails permanently without crash or retry."""
        self.mock_client.embed.side_effect = EmbeddingPermanentError("HTTP 422: Input text exceeds maximum context length of 4096 tokens.")

        result = self.service.generate_embedding_for_job(self.job)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("EmbeddingPermanentError", result.error_message)

        job_emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)



class JobEmbeddingTaskTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_task@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Task Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Task Company",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior DevOps Engineer",
            description="Manage Terraform, AWS, and Kubernetes infrastructure.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            work_type="remote",
            status=Job.Status.ACTIVE,
        )

    @patch("matching.job_embeddings.NvidiaEmbeddingClient")
    def test_task_successful_execution_and_sanitized_result(self, mock_client_cls):
        """Task runs successfully and returns sanitized result payload."""
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = EmbeddingResult(
            embedding=make_dummy_vector(),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )
        mock_client_cls.return_value = mock_client

        res = generate_job_embedding_task(str(self.job.id))

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["dimensions"], TARGET_EMBEDDING_DIMENSIONS)
        self.assertFalse(res["is_unchanged"])
        self.assertFalse(res["is_stale"])
        self.assertIsNone(res["error"])

    @patch("matching.job_embeddings.NvidiaEmbeddingClient")
    def test_task_transient_error_retried_with_backoff(self, mock_client_cls):
        """Transient error triggers celery retry with exponential backoff."""
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.side_effect = EmbeddingTransientError("Gateway 504")
        mock_client_cls.return_value = mock_client

        task = generate_job_embedding_task
        task.retry = MagicMock(side_effect=Exception("RetryTriggered"))
        task.request.retries = 1

        with self.assertRaises(Exception) as cm:
            task(str(self.job.id))

        self.assertIn("RetryTriggered", str(cm.exception))
        # Attempt 2 -> 2**1 * 5 = 10s countdown
        task.retry.assert_called_once()
        _, retry_kwargs = task.retry.call_args
        self.assertEqual(retry_kwargs["countdown"], 10)

    @patch("matching.job_embeddings.NvidiaEmbeddingClient")
    def test_task_rate_limit_error_uses_retry_after(self, mock_client_cls):
        """Rate limit error with retry_after header respects that duration."""
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        rate_err = EmbeddingRateLimitError("Rate limit exceeded")
        rate_err.retry_after = 45
        mock_client.embed.side_effect = rate_err
        mock_client_cls.return_value = mock_client

        task = generate_job_embedding_task
        task.retry = MagicMock(side_effect=Exception("RetryTriggered"))
        task.request.retries = 0

        with self.assertRaises(Exception):
            task(str(self.job.id))

        task.retry.assert_called_once()
        _, retry_kwargs = task.retry.call_args
        self.assertEqual(retry_kwargs["countdown"], 45)

    @patch("matching.job_embeddings.NvidiaEmbeddingClient")
    def test_task_excessive_retry_after_capped_at_max_retry_delay(self, mock_client_cls):
        """Excessive retry_after (e.g. 999,999s) is strictly capped at MAX_TASK_RETRY_DELAY (300s)."""
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        rate_err = EmbeddingRateLimitError("Rate limit exceeded")
        rate_err.retry_after = 999999
        mock_client.embed.side_effect = rate_err
        mock_client_cls.return_value = mock_client

        task = generate_job_embedding_task
        task.retry = MagicMock(side_effect=Exception("RetryTriggered"))
        task.request.retries = 0

        with self.assertRaises(Exception):
            task(str(self.job.id))

        task.retry.assert_called_once()
        _, retry_kwargs = task.retry.call_args
        self.assertEqual(retry_kwargs["countdown"], MAX_TASK_RETRY_DELAY)
        self.assertEqual(MAX_TASK_RETRY_DELAY, 300)

    @patch("matching.job_embeddings.NvidiaEmbeddingClient")
    def test_task_permanent_input_too_long_does_not_retry(self, mock_client_cls):
        """Permanent input too long error does not retry and returns status failed."""
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.side_effect = EmbeddingPermanentError("HTTP 422: Input too long")
        mock_client_cls.return_value = mock_client

        task = generate_job_embedding_task
        task.retry = MagicMock()

        res = task(str(self.job.id))

        task.retry.assert_not_called()
        self.assertEqual(res["status"], "failed")
        self.assertIn("EmbeddingPermanentError", res["error"])
