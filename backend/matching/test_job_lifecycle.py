"""
Phase 10.3: Employer Job Lifecycle Signal Integration & Matching Trigger Tests.

Strict Safety:
- All NVIDIA API interactions are mocked. Zero live external API calls.
- Runs exclusively on isolated PostgreSQL test database with --keepdb.
- Zero live Resend/email interactions, zero migrations, zero Celery worker processes.

Covers:
1. Creating an active first-party job schedules embedding after commit.
2. Creating an inactive job does not schedule active-job matching.
3. Activating a previously inactive job schedules embedding.
4. Editing material content on an active job schedules embedding.
5. Updating an unrelated field does not schedule unnecessary embedding work.
6. A rolled-back transaction does not dispatch the task.
7. Successful embedding generation schedules job matching.
8. Failed embedding generation does not schedule matching.
9. Deactivated jobs cannot be matched by stale tasks.
10. Stale embedding results cannot overwrite newer content.
11. Duplicate task delivery remains idempotent.
12. External Himalayas, Adzuna, and People Prime ATS jobs never enter the first-party pipeline.
13. Existing scoring thresholds, candidate eligibility, approval gates, and match uniqueness remain intact.
14. Notification outbox records are not duplicated by repeated matching.
"""

from unittest.mock import MagicMock, call, patch
import uuid
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from external_jobs.models import ExternalJob, ExternalJobSource
from common.embedding_client import (
    EmbeddingPermanentError,
    EmbeddingResult,
)
from jobs.models import Job
from matching.job_embeddings import (
    JobEmbeddingService,
    JobTextPreparationService,
    is_eligible_first_party_job,
)
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    CandidateResumeEmbedding,
    EmbeddingStatus,
    JobEmbedding,
    Match,
)
from matching.tasks import (
    generate_job_embedding_task,
    run_matching_for_job_task,
)
from notifications.models import NotificationOutbox, NotificationType


def make_dummy_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS, val: float = 0.05) -> list[float]:
    return [val] * dim


class JobLifecycleSignalAndMatchingTests(TestCase):
    def setUp(self):
        super().setUp()

        # Create Employer & Company
        self.employer_user = User.objects.create_user(
            email="employer_lifecycle@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Test",
        )
        self.company = Company.objects.create(
            name="Prime Tech Solutions",
            owner=self.employer_user,
            profile_complete=True,
        )

        # Create Candidate User & Profile
        self.candidate_user = User.objects.create_user(
            email="candidate_lifecycle@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Candidate Test",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Staff Distributed Systems Architect",
            current_title="Software Architect",
            years_experience=8,
            skills=["Python", "Django", "PostgreSQL", "Celery", "Distributed Systems"],
            experience_level=CandidateProfile.ExperienceLevel.LEAD,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            open_to_matching=True,
            profile_complete=True,
            resume_url="resumes/test_candidate/resume.pdf",
        )

        # Create Candidate Resume Embedding (completed, 2048-dim)
        from common.resume_extraction import calculate_source_fingerprint
        self.candidate_vector = make_dummy_vector(TARGET_EMBEDDING_DIMENSIONS, 0.05)
        self.candidate_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.candidate_vector,
            content_hash="test_candidate_hash",
            version=calculate_source_fingerprint("resumes/test_candidate/resume.pdf"),
            extracted_text="Experienced staff software architect specializing in Python, Django, PostgreSQL, Celery, and distributed systems.",
            embedded_at=timezone.now(),
        )

    # 1. Creating an active first-party job schedules embedding after commit
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_create_active_first_party_job_schedules_embedding_after_commit(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            job = Job.objects.create(
                company=self.company,
                posted_by=self.employer_user,
                title="Staff Backend Engineer",
                description="Lead our backend team building Python and Django systems.",
                role_type=Job.RoleType.FULL_TIME,
                experience_level=Job.ExperienceLevel.LEAD,
                tech_stack=["Python", "Django", "PostgreSQL"],
                status=Job.Status.ACTIVE,
            )

        mock_delay.assert_called_once_with(str(job.id))

    # 2. Creating an inactive job does not schedule active-job matching or embedding
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_create_inactive_job_does_not_schedule_embedding(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            Job.objects.create(
                company=self.company,
                posted_by=self.employer_user,
                title="Draft Backend Engineer",
                description="Draft description not yet published.",
                role_type=Job.RoleType.FULL_TIME,
                experience_level=Job.ExperienceLevel.MID,
                status=Job.Status.DRAFT,
            )

        mock_delay.assert_not_called()

    # 3. Activating a previously inactive job schedules embedding
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_activating_inactive_job_schedules_embedding(self, mock_delay):
        draft_job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Paused Backend Engineer",
            description="Initially paused role.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.PAUSED,
        )
        mock_delay.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            draft_job.status = Job.Status.ACTIVE
            draft_job.save()

        mock_delay.assert_called_once_with(str(draft_job.id))

    # 4. Editing material content on an active job schedules embedding and invalidates old
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_editing_material_content_on_active_job_schedules_embedding(self, mock_delay):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Engineer",
            description="Original description.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python"],
            status=Job.Status.ACTIVE,
        )
        # Seed an existing completed embedding
        emb = JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(),
            content_hash="old_content_hash",
            embedded_at=timezone.now(),
        )
        mock_delay.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            job.description = "Completely overhauled description requiring new passage vectors."
            job.tech_stack = ["Python", "FastAPI", "PostgreSQL", "Kafka"]
            job.save()

        mock_delay.assert_called_once_with(str(job.id))
        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.PENDING)
        self.assertIsNone(emb.embedding)

    # 5. Updating an unrelated field does not schedule unnecessary embedding work
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_updating_unrelated_field_does_not_schedule_embedding(self, mock_delay):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Stable Role",
            description="Stable description.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            salary_range="$100k - $120k",
            featured=False,
            status=Job.Status.ACTIVE,
        )
        mock_delay.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            job.salary_range = "$140,000 - $170,000"
            job.featured = True
            job.jd_quality_score = 95
            job.jd_quality_feedback = "Excellent job posting."
            job.save()

        mock_delay.assert_not_called()

    # 6. A rolled-back transaction does not dispatch the task
    @patch("matching.tasks.generate_job_embedding_task.delay")
    def test_rolled_back_transaction_does_not_dispatch_task(self, mock_delay):
        try:
            with transaction.atomic():
                Job.objects.create(
                    company=self.company,
                    posted_by=self.employer_user,
                    title="Rollback Job",
                    description="This job should never be committed.",
                    role_type=Job.RoleType.FULL_TIME,
                    experience_level=Job.ExperienceLevel.MID,
                    status=Job.Status.ACTIVE,
                )
                raise ValueError("Simulated database failure")
        except ValueError:
            pass

        mock_delay.assert_not_called()
        self.assertFalse(Job.objects.filter(title="Rollback Job").exists())

    # 7. Successful embedding generation schedules job matching
    @patch("matching.tasks.run_matching_for_job_task.delay")
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_successful_embedding_generation_schedules_matching(self, mock_embed, mock_matching_delay):
        dummy_vector = make_dummy_vector(TARGET_EMBEDDING_DIMENSIONS, 0.05)
        mock_embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            token_count=50,
        )

        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Architect",
            description="Designing high throughput architectures in Python.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.ACTIVE,
        )

        result = generate_job_embedding_task(str(job.id))

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["matching_scheduled"])
        mock_matching_delay.assert_called_once_with(str(job.id))

        # Check JobEmbedding persisted in db
        emb = JobEmbedding.objects.get(job=job)
        self.assertEqual(emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(len(emb.embedding), TARGET_EMBEDDING_DIMENSIONS)

    # 8. Failed embedding generation does not schedule matching
    @patch("matching.tasks.run_matching_for_job_task.delay")
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_failed_embedding_generation_does_not_schedule_matching(self, mock_embed, mock_matching_delay):
        mock_embed.side_effect = EmbeddingPermanentError("Permanent failure from model API")

        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Failing Job",
            description="Testing embedding permanent failure.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.MID,
            status=Job.Status.ACTIVE,
        )

        result = generate_job_embedding_task(str(job.id))

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result.get("matching_scheduled", False))
        mock_matching_delay.assert_not_called()

        emb = JobEmbedding.objects.get(job=job)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)

    # 9. Deactivated jobs cannot be matched by stale tasks and have embeddings invalidated
    def test_deactivated_jobs_cannot_be_matched_and_are_invalidated(self):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Deactivated Lead Engineer",
            description="Active role that gets closed.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(),
            content_hash="active_hash",
            embedded_at=timezone.now(),
        )

        # Deactivate job to CLOSED
        job.status = Job.Status.CLOSED
        job.save()

        # Embedding must be invalidated to FAILED with cleared vector
        emb = JobEmbedding.objects.get(job=job)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)

        # Run hybrid matching for the job; must match 0
        from matching.hybrid_engine import HybridMatchingEngine
        match_result = HybridMatchingEngine.run_matching_for_job(str(job.id))
        self.assertEqual(match_result["matched"], 0)
        self.assertIn("only 'active' jobs are eligible", match_result.get("reason", ""))

    # 10. Stale embedding results cannot overwrite newer content
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_stale_embedding_result_cannot_overwrite_newer_content(self, mock_embed):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Original Title",
            description="Original description text for embedding.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.ACTIVE,
        )

        # Hook into client.embed: while embed is running, update the job description in db!
        def side_effect_embed(*args, **kwargs):
            Job.objects.filter(id=job.id).update(
                description="Concurrently updated description while slow embed ran.",
                updated_at=timezone.now(),
            )
            return EmbeddingResult(
                embedding=make_dummy_vector(),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
                token_count=50,
            )

        mock_embed.side_effect = side_effect_embed

        service = JobEmbeddingService()
        result = service.generate_embedding_for_job(job.id)

        # Stale task protection must catch this and discard stale vector
        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message)

    # 11. Duplicate task delivery remains idempotent
    @patch("matching.tasks.run_matching_for_job_task.delay")
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_duplicate_task_delivery_is_idempotent(self, mock_embed, mock_matching_delay):
        dummy_vector = make_dummy_vector(TARGET_EMBEDDING_DIMENSIONS, 0.05)
        mock_embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            token_count=50,
        )

        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Idempotent Test Engineer",
            description="Testing idempotent task execution.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.MID,
            status=Job.Status.ACTIVE,
        )

        # First task execution
        res1 = generate_job_embedding_task(str(job.id))
        self.assertEqual(res1["status"], "completed")
        self.assertFalse(res1["is_unchanged"])
        self.assertEqual(mock_embed.call_count, 1)

        # Second task execution (duplicate delivery)
        res2 = generate_job_embedding_task(str(job.id))
        self.assertEqual(res2["status"], "completed")
        self.assertTrue(res2["is_unchanged"])
        # NVIDIA API must NOT have been called a second time
        self.assertEqual(mock_embed.call_count, 1)

    # 12. External Himalayas, Adzuna, and People Prime ATS jobs never enter first-party pipeline
    def test_external_jobs_never_enter_first_party_pipeline(self):
        external_source = ExternalJobSource.objects.create(
            name="Himalayas",
            provider_code="himalayas",
            api_enabled=True,
            attribution_name="Himalayas Remote",
        )
        external_job = ExternalJob.objects.create(
            source=external_source,
            external_job_id="himalayas-404",
            title="External Himalayas Engineer",
            company_name="Remote Co",
            description="Scraped remote job from Himalayas.",
            original_job_url="https://example.com/himalayas/404",
            source_name="Himalayas",
            status=ExternalJob.Status.ACTIVE,
        )

        # 1. ExternalJob model cannot be evaluated by first-party eligibility helper
        eligible, reason = is_eligible_first_party_job(external_job)
        self.assertFalse(eligible)
        self.assertIn("not an instance of first-party Job model", reason)

        # 2. First-party Job without company or posted_by is also rejected
        orphan_job = Job(
            title="Orphan Job",
            description="Has no company.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.MID,
            status=Job.Status.ACTIVE,
        )
        eligible_orphan, reason_orphan = is_eligible_first_party_job(orphan_job)
        self.assertFalse(eligible_orphan)
        self.assertIn("not associated with an employer Company", reason_orphan)

    # 13. Existing scoring thresholds, candidate eligibility, approval gates, and match uniqueness
    def test_scoring_thresholds_candidate_eligibility_and_approval_gates(self):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Staff Distributed Systems Architect",
            description="Build high-performance distributed systems in Python and Django.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Python", "Django", "PostgreSQL", "Celery", "Distributed Systems"],
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.candidate_vector,  # Exact match vector -> 100% semantic
            content_hash=JobTextPreparationService.prepare_text(job).content_hash,
            embedded_at=timezone.now(),
        )

        from matching.hybrid_engine import HybridMatchingEngine

        # Candidate is eligible -> Run matching
        result = HybridMatchingEngine.run_matching_for_job(str(job.id))
        self.assertEqual(result["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job=job)
        self.assertGreater(match.match_score, 70)
        # Approval gate: visible_to_employer is strictly False initially
        self.assertFalse(match.visible_to_employer)
        self.assertEqual(match.status, Match.Status.SUGGESTED)

        # Candidate becomes ineligible (e.g. open_to_matching=False)
        self.candidate_profile.open_to_matching = False
        self.candidate_profile.save()

        # Another job matching run must NOT match ineligible candidate
        job2 = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Staff Python Lead",
            description="Another python role.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Python"],
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(
            job=job2,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.candidate_vector,
            content_hash=JobTextPreparationService.prepare_text(job2).content_hash,
            embedded_at=timezone.now(),
        )
        result2 = HybridMatchingEngine.run_matching_for_job(str(job2.id))
        self.assertEqual(result2["matched"], 0)

    # 14. Notification outbox records are not duplicated by repeated matching
    def test_notification_outbox_not_duplicated_by_repeated_matching(self):
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="High Match Architect",
            description="Direct match for our candidate.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Python", "Django", "PostgreSQL", "Celery", "Distributed Systems"],
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.candidate_vector,  # Identical vector -> score 100% (>= 85%)
            content_hash=JobTextPreparationService.prepare_text(job).content_hash,
            embedded_at=timezone.now(),
        )

        from matching.hybrid_engine import HybridMatchingEngine

        # Run 1
        HybridMatchingEngine.run_matching_for_job(str(job.id))
        match = Match.objects.get(candidate_profile=self.candidate_profile, job=job)
        self.assertGreaterEqual(match.match_score, 85)

        initial_outbox_count = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).count()
        self.assertEqual(initial_outbox_count, 1)

        # Run 2 (Repeated matching)
        HybridMatchingEngine.run_matching_for_job(str(job.id))

        subsequent_outbox_count = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).count()
        self.assertEqual(subsequent_outbox_count, 1)
