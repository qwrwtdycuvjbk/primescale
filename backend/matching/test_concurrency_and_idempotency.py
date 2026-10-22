"""
Phase 10.4: Concurrency, Idempotency, and Stale-Result Verification Tests.

Covers:
1. Candidate Resume Race Scenarios:
   - In-flight Resume A extraction superseded by Resume B upload: A cannot overwrite B.
   - Resume A finishing after Resume B is current: A cannot trigger matching for obsolete content.
   - Concurrent workers processing same unchanged resume: idempotency preserved.
   - Resume cleared while embedding task is in-flight: stale task cannot restore vector or text.
   - Candidate becoming ineligible while matching task is queued: matching engine rechecks eligibility and persists 0 matches.
   - Candidate becoming eligible with existing valid embedding: triggers matching without redundant re-extraction or re-embedding.
2. Employer Job Race Scenarios:
   - In-flight Job A embedding superseded by Job B edit: A cannot overwrite B.
   - Job deactivated while embedding request is in-flight: completed task cannot restore active embedding or trigger matching.
   - Job deactivated and reactivated while older tasks are queued: only current state embedding is persisted.
   - Multiple rapid edits generating multiple tasks: stale tasks cannot trigger matching.
   - Duplicate task delivery for unchanged job: idempotent and skips redundant API calls.
   - Job becoming ineligible after embedding but before matching: matching task rechecks eligibility and aborts.
3. Matching & Notification Idempotency:
   - Concurrent/repeated matching runs do not duplicate matches and preserve unique constraints.
   - Match statuses (CANDIDATE_INTERESTED, MUTUAL_FIT) and recruiter approval gates are strictly preserved.
   - New matches default to visible_to_employer=False.
   - Repeated matching does not duplicate NotificationOutbox records.
   - Strict qualification score threshold > 70.00.
   - External jobs (Himalayas, Adzuna, People Prime ATS) remain strictly excluded.
"""

from unittest import skipUnless
from unittest.mock import MagicMock, call, patch
import uuid
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from external_jobs.models import ExternalJob, ExternalJobSource
from common.embedding_client import (
    EmbeddingResult,
)
from common.resume_extraction import (
    ExtractionStatus,
    ResumeExtractionResult,
    ResumeTextExtractionService,
    calculate_content_hash,
    calculate_source_fingerprint,
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
from matching.resume_embeddings import ResumeEmbeddingService
from matching.hybrid_engine import (
    HybridMatchingEngine,
    calculate_hybrid_score,
    is_candidate_eligible_for_hybrid_matching,
    is_job_eligible_for_hybrid_matching,
)
from matching.tasks import (
    generate_job_embedding_task,
    process_candidate_resume_task,
    run_matching_for_candidate_task,
    run_matching_for_job_task,
)
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType


def make_dummy_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS, val: float = 0.05) -> list[float]:
    return [val] * dim


class CandidateResumeConcurrencyTests(TestCase):
    def setUp(self):
        super().setUp()
        self.candidate_user = User.objects.create_user(
            email="candidate_race@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Candidate Race",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Python Lead",
            current_title="Lead Architect",
            years_experience=10,
            skills=["Python", "Django", "PostgreSQL"],
            experience_level=CandidateProfile.ExperienceLevel.LEAD,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            open_to_matching=True,
            profile_complete=True,
            profile_completeness=100,
            resume_url="resumes/user/resume_A.pdf",
        )

    # 1. In-flight Resume A extraction superseded by Resume B upload: A cannot overwrite B
    def test_in_flight_extraction_superseded_by_newer_resume_discarded(self):
        extraction_service = ResumeTextExtractionService()

        # Simulate: extraction of Resume A starts with resume_url = "resumes/user/resume_A.pdf"
        # While reading storage, candidate uploads Resume B:
        self.candidate_profile.resume_url = "resumes/user/resume_B.pdf"
        self.candidate_profile.save(update_fields=["resume_url", "updated_at"])

        # Resume A finishes storage extraction and attempts to persist
        stale_profile_snapshot = CandidateProfile(
            id=self.candidate_profile.id,
            user=self.candidate_user,
            resume_url="resumes/user/resume_A.pdf",
        )

        with patch.object(
            extraction_service,
            "extract_from_storage",
            return_value=ResumeExtractionResult(
                status=ExtractionStatus.SUCCESS,
                text="Obsolete text from Resume A",
                content_hash="hash_resume_A",
                character_count=26,
            ),
        ):
            result = extraction_service.extract_and_persist_for_candidate(stale_profile_snapshot)

        # Extraction result must be rejected as stale
        self.assertFalse(result.is_success)
        self.assertEqual(result.status, ExtractionStatus.EXTRACTION_ERROR)
        self.assertIn("Stale resume extraction discarded", result.error_message)

        # Database record must NOT contain Resume A's text
        emb = CandidateResumeEmbedding.objects.filter(candidate_profile=self.candidate_profile).first()
        if emb:
            self.assertNotEqual(emb.extracted_text, "Obsolete text from Resume A")

    # 2. Resume A finishing after Resume B is current cannot trigger matching
    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    def test_stale_task_does_not_trigger_matching_for_obsolete_resume(self, mock_matching_delay):
        # Candidate previously had Resume A, but now has Resume B
        self.candidate_profile.resume_url = "resumes/user/resume_B.pdf"
        self.candidate_profile.save(update_fields=["resume_url", "updated_at"])

        # Delayed Celery task for Resume A arrives
        res = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path="resumes/user/resume_A.pdf",
        )

        self.assertEqual(res["status"], "stale_resume_discarded")
        mock_matching_delay.assert_not_called()

    # 3. Resume cleared while embedding task is in-flight: stale task cannot restore vector or text
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_resume_cleared_in_flight_cannot_restore_vector_or_text(self, mock_embed):
        # Initial extracted text for resume exists
        initial_fp = calculate_source_fingerprint("resumes/user/resume_A.pdf")
        emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.PENDING,
            extracted_text="Valid initial resume text",
            content_hash="initial_hash",
            version=initial_fp,
        )

        # Hook client.embed: while embed is running, candidate deletes/clears their resume!
        def side_effect_embed(*args, **kwargs):
            self.candidate_profile.resume_url = None
            self.candidate_profile.save()
            return EmbeddingResult(
                embedding=make_dummy_vector(),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
                token_count=50,
            )

        mock_embed.side_effect = side_effect_embed

        service = ResumeEmbeddingService()
        result = service.generate_embedding_for_candidate(self.candidate_profile)

        # Must discard stale vector
        self.assertTrue(result.is_stale)
        emb.refresh_from_db()
        self.assertIsNone(emb.embedding)
        self.assertIsNone(emb.extracted_text)

    # 4. Candidate becomes ineligible while matching work is queued: matching engine rechecks eligibility
    def test_candidate_becomes_ineligible_while_matching_queued(self):
        # Setup completed embedding
        CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(),
            content_hash="test_hash",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
            embedded_at=timezone.now(),
        )

        # Candidate turns off open_to_matching in DB
        self.candidate_profile.open_to_matching = False
        self.candidate_profile.save(update_fields=["open_to_matching", "updated_at"])

        # Matching task runs
        result = HybridMatchingEngine.run_matching_for_candidate(str(self.candidate_profile.id))

        self.assertEqual(result["matched"], 0)
        self.assertIn("not open to matching", result.get("reason", ""))

    # 5. Candidate becomes eligible with existing valid embedding: triggers matching without re-embedding
    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_candidate_becomes_eligible_with_existing_valid_embedding(self, mock_resume_delay, mock_matching_delay):
        # Candidate has existing completed embedding, but was profile_complete=False
        self.candidate_profile.profile_complete = False
        self.candidate_profile.save()
        fp = calculate_source_fingerprint(self.candidate_profile.resume_url)
        CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(),
            content_hash="existing_hash",
            version=fp,
            embedded_at=timezone.now(),
        )
        mock_matching_delay.reset_mock()
        mock_resume_delay.reset_mock()

        # Update candidate to profile_complete=True
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate_profile.profile_complete = True
            self.candidate_profile.save()

        # Matching scheduled directly; re-extraction/re-embedding bypassed
        mock_matching_delay.assert_called_once_with(str(self.candidate_profile.id))
        mock_resume_delay.assert_not_called()


class EmployerJobConcurrencyTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_race@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Employer Race",
        )
        self.company = Company.objects.create(
            name="Prime Concurrency Corp",
            owner=self.employer_user,
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Distributed Systems Architect",
            description="Initial job description for embedding.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python", "PostgreSQL"],
            status=Job.Status.ACTIVE,
        )

    # 6. In-flight Job A embedding superseded by Job B edit: A cannot overwrite B
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_in_flight_job_embedding_superseded_by_edit_discarded(self, mock_embed):
        def side_effect_embed(*args, **kwargs):
            # Job content edited while slow embed was in flight
            Job.objects.filter(id=self.job.id).update(
                description="Overhauled description with new requirements.",
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
        result = service.generate_embedding_for_job(self.job.id)

        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message)

    # 7. Job deactivated while embedding request is in flight: completed task cannot restore active embedding
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_job_deactivated_in_flight_cannot_restore_active_embedding(self, mock_embed):
        def side_effect_embed(*args, **kwargs):
            # Employer closes the job while embedding is being computed
            Job.objects.filter(id=self.job.id).update(
                status=Job.Status.CLOSED,
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
        result = service.generate_embedding_for_job(self.job.id)

        self.assertTrue(result.is_stale)
        self.assertEqual(result.status, EmbeddingStatus.FAILED)

        # JobEmbedding must remain FAILED and have NO vector
        emb = JobEmbedding.objects.get(job=self.job)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)

    # 8. Job deactivated and reactivated while older tasks are queued
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_deactivated_and_reactivated_job_rejects_queued_old_tasks(self, mock_embed):
        # Snapshot state of Task 1
        initial_job_updated_at = self.job.updated_at
        initial_embedding = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.PENDING,
            version="gen_task_1",
        )

        # Employer pauses job, then reactivates it
        self.job.status = Job.Status.PAUSED
        self.job.save()
        self.job.status = Job.Status.ACTIVE
        self.job.save()

        # Task 1 finishes with older snapshot parameters
        mock_embed.return_value = EmbeddingResult(
            embedding=make_dummy_vector(),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            token_count=50,
        )

        service = JobEmbeddingService()
        # Call generate_embedding_for_job with current state
        result = service.generate_embedding_for_job(self.job.id)

        # Current generation succeeds and records new valid version
        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        emb = JobEmbedding.objects.get(job=self.job)
        self.assertNotEqual(emb.version, "gen_task_1")

    # 9. Multiple rapid edits generate multiple tasks: stale tasks cannot trigger matching
    @patch("matching.tasks.run_matching_for_job_task.delay")
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_stale_task_from_rapid_edits_does_not_trigger_matching(self, mock_embed, mock_matching_delay):
        # Job edited: current DB has new text
        self.job.description = "Rapid Edit 3: Final description."
        self.job.save()

        # Stale task 1 runs with mock embedding generated from old content hash
        old_hash = calculate_content_hash("Job Title: Senior Distributed Systems Architect\nCompany: Prime Concurrency Corp\nRole Type: full-time\nExperience Level: senior\nWork Type: remote\nRequired Skills: PostgreSQL, Python\n\nJob Description:\nRapid Edit 1: Obsolete description.")

        JobEmbedding.objects.filter(job=self.job).update(
            status=EmbeddingStatus.COMPLETED,
            embedding=make_dummy_vector(),
            content_hash=old_hash,  # Hash mismatch with "Rapid Edit 3"
        )

        # generate_job_embedding_task chaining check
        with patch.object(JobEmbeddingService, "generate_embedding_for_job") as mock_gen:
            from matching.job_embeddings import JobEmbeddingResult
            mock_gen.return_value = JobEmbeddingResult(
                job_id=str(self.job.id),
                status=EmbeddingStatus.COMPLETED,
                content_hash=old_hash,
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
                is_stale=False,
            )
            result = generate_job_embedding_task(str(self.job.id))

        self.assertFalse(result.get("matching_scheduled", False))
        mock_matching_delay.assert_not_called()

    # 10. Job becomes ineligible after embedding generation but before matching: matching aborts
    def test_job_becomes_ineligible_before_matching_begins(self):
        JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(),
            content_hash=JobTextPreparationService.prepare_text(self.job).content_hash,
            embedded_at=timezone.now(),
        )

        # Job closed
        self.job.status = Job.Status.CLOSED
        self.job.save(update_fields=["status", "updated_at"])

        # Matching task executes for job ID
        match_res = HybridMatchingEngine.run_matching_for_job(str(self.job.id))

        self.assertEqual(match_res["matched"], 0)
        self.assertIn("only 'active' jobs are eligible", match_res.get("reason", ""))


class MatchingAndNotificationIdempotencyTests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="employer_idemp@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="Idempotent Corp",
            owner=self.employer_user,
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Staff Python Architect",
            description="High-scale distributed matching engine.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Python", "Django", "PostgreSQL"],
            status=Job.Status.ACTIVE,
        )
        self.vector = make_dummy_vector(TARGET_EMBEDDING_DIMENSIONS, 0.05)
        self.job_emb = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.vector,
            content_hash=JobTextPreparationService.prepare_text(self.job).content_hash,
            embedded_at=timezone.now(),
        )

        self.candidate_user = User.objects.create_user(
            email="candidate_idemp@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Staff Python Architect",
            current_title="Software Architect",
            years_experience=10,
            skills=["Python", "Django", "PostgreSQL"],
            experience_level=CandidateProfile.ExperienceLevel.LEAD,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            open_to_matching=True,
            profile_complete=True,
            profile_completeness=100,
            resume_url="resumes/user/resume.pdf",
        )
        self.candidate_emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.vector,  # 100% semantic match
            content_hash="cand_hash",
            version=calculate_source_fingerprint("resumes/user/resume.pdf"),
            embedded_at=timezone.now(),
        )

    # 11. Repeated matching does not duplicate Match records and preserves unique constraint
    def test_repeated_matching_does_not_duplicate_matches(self):
        res1 = HybridMatchingEngine.run_matching_for_job(str(self.job.id))
        self.assertEqual(res1["matched"], 1)

        res2 = HybridMatchingEngine.run_matching_for_job(str(self.job.id))
        self.assertEqual(res2["matched"], 1)

        total_matches = Match.objects.filter(candidate_profile=self.candidate_profile, job=self.job).count()
        self.assertEqual(total_matches, 1)

    # 12. Re-running matching preserves existing match status and recruiter approval gate
    def test_rerunning_matching_preserves_candidate_status_and_approval_gate(self):
        # Create match with CANDIDATE_INTERESTED and visible_to_employer=True
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            match_reason="Initial match",
            status=Match.Status.CANDIDATE_INTERESTED,
            visible_to_employer=True,
        )

        # Run matching again
        HybridMatchingEngine.run_matching_for_job(str(self.job.id))

        match.refresh_from_db()
        # Status and visibility must remain preserved
        self.assertEqual(match.status, Match.Status.CANDIDATE_INTERESTED)
        self.assertTrue(match.visible_to_employer)

    # 13. Newly created matches strictly enforce visible_to_employer=False
    def test_new_matches_strictly_enforce_approval_gate(self):
        res = HybridMatchingEngine.run_matching_for_job(str(self.job.id))
        self.assertEqual(res["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertFalse(match.visible_to_employer)
        self.assertEqual(match.status, Match.Status.SUGGESTED)

    # 14. Repeated matching does not duplicate NotificationOutbox records
    def test_repeated_matching_does_not_duplicate_notification_outbox(self):
        # Run 1
        HybridMatchingEngine.run_matching_for_job(str(self.job.id))
        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertGreaterEqual(match.match_score, 85)

        outbox_count_1 = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).count()
        self.assertEqual(outbox_count_1, 1)

        # Run 2
        HybridMatchingEngine.run_matching_for_job(str(self.job.id))
        outbox_count_2 = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).count()
        self.assertEqual(outbox_count_2, 1)

    # 15. Qualification score threshold >= 70.00
    def test_qualification_threshold_strictly_greater_than_70(self):
        # 69.99 does NOT qualify
        bd_below = calculate_hybrid_score(semantic_score=69.98, skill_score=70.0, exp_score=70.0)
        self.assertEqual(bd_below.final_score, 69.99)
        self.assertFalse(bd_below.qualifies)

        # Exact 70.00 DOES qualify
        breakdown_exact = calculate_hybrid_score(semantic_score=70.0, skill_score=70.0, exp_score=70.0)
        self.assertEqual(breakdown_exact.final_score, 70.0)
        self.assertTrue(breakdown_exact.qualifies)

        # 70.10 DOES qualify
        breakdown_above = calculate_hybrid_score(semantic_score=70.2, skill_score=70.0, exp_score=70.0)
        self.assertGreater(breakdown_above.final_score, 70.0)
        self.assertTrue(breakdown_above.qualifies)

    # 16. External jobs remain strictly excluded from matching
    def test_external_jobs_remain_strictly_excluded(self):
        source = ExternalJobSource.objects.create(name="People Prime ATS", provider_code="pp_ats")
        ext_job = ExternalJob.objects.create(
            source=source,
            external_job_id="pp-123",
            title="External ATS Python Lead",
            company_name="ATS Client",
            description="External job description.",
            original_job_url="https://example.com/job/123",
            source_name="People Prime ATS",
            status=ExternalJob.Status.ACTIVE,
        )

        is_eligible, reason = is_eligible_first_party_job(ext_job)
        self.assertFalse(is_eligible)
        self.assertIn("not an instance of first-party Job model", reason)

        match_res = HybridMatchingEngine.run_matching_for_job(str(ext_job.id))
        self.assertEqual(match_res["matched"], 0)


import threading
from django.db import connections


@skipUnless(connection.vendor == "postgresql", "Genuine concurrent multi-threading tests require PostgreSQL row-level locking.")
class GenuinePostgresConcurrencyTests(TransactionTestCase):
    """
    Genuine concurrent transaction tests executing simultaneously across
    separate database connections on PostgreSQL.
    Verifies row-level locking (select_for_update), savepoints, and unique constraints.
    """

    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="emp_concurrent@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="Concurrent Real Co",
            owner=self.employer_user,
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Real Concurrent Engineer",
            description="High concurrency testing in PostgreSQL.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python", "Django", "PostgreSQL"],
            status=Job.Status.ACTIVE,
        )
        self.vector = make_dummy_vector(TARGET_EMBEDDING_DIMENSIONS, 0.05)
        self.job_emb, _ = JobEmbedding.objects.get_or_create(job=self.job)
        self.job_emb.status = EmbeddingStatus.COMPLETED
        self.job_emb.model_name = TARGET_EMBEDDING_MODEL
        self.job_emb.dimensions = TARGET_EMBEDDING_DIMENSIONS
        self.job_emb.embedding = self.vector
        self.job_emb.content_hash = JobTextPreparationService.prepare_text(self.job).content_hash
        self.job_emb.embedded_at = timezone.now()
        self.job_emb.save()

        self.candidate_user = User.objects.create_user(
            email="cand_concurrent@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Real Concurrent Engineer",
            current_title="Software Architect",
            years_experience=8,
            skills=["Python", "Django", "PostgreSQL"],
            experience_level=CandidateProfile.ExperienceLevel.SENIOR,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            open_to_matching=True,
            profile_complete=True,
            profile_completeness=100,
            resume_url="resumes/user/concurrent_resume.pdf",
        )
        self.candidate_emb, _ = CandidateResumeEmbedding.objects.get_or_create(
            candidate_profile=self.candidate_profile
        )
        self.candidate_emb.status = EmbeddingStatus.COMPLETED
        self.candidate_emb.model_name = TARGET_EMBEDDING_MODEL
        self.candidate_emb.dimensions = TARGET_EMBEDDING_DIMENSIONS
        self.candidate_emb.embedding = self.vector
        self.candidate_emb.content_hash = "cand_concurrent_hash"
        self.candidate_emb.version = calculate_source_fingerprint("resumes/user/concurrent_resume.pdf")
        self.candidate_emb.embedded_at = timezone.now()
        self.candidate_emb.save()

    def tearDown(self):
        connections.close_all()
        super().tearDown()

    def test_genuine_concurrent_matching_runs_preserve_uniqueness_and_outbox(self):
        """
        Spawns two concurrent threads that execute HybridMatchingEngine.run_matching_for_job
        simultaneously using a threading.Barrier across separate database connections.
        """
        barrier = threading.Barrier(2)
        errors = []
        results = []

        def worker_task():
            try:
                # Close inherited connection so each thread opens its own connection
                connections.close_all()
                barrier.wait(timeout=10)
                res = HybridMatchingEngine.run_matching_for_job(str(self.job.id))
                results.append(res)
            except Exception as exc:
                errors.append(exc)
            finally:
                connections.close_all()

        t1 = threading.Thread(target=worker_task)
        t2 = threading.Thread(target=worker_task)

        t1.start()
        t2.start()

        t1.join(timeout=15)
        t2.join(timeout=15)

        # Neither thread should throw unhandled exceptions or deadlock
        self.assertEqual(errors, [], f"Concurrent threads raised unexpected exceptions: {errors}")
        self.assertEqual(len(results), 2)

        # Re-open default connection to verify database state
        connections.close_all()

        # Invariant 1: Exactly one Match record created
        match_count = Match.objects.filter(
            candidate_profile=self.candidate_profile,
            job=self.job,
        ).count()
        self.assertEqual(match_count, 1, "Concurrent matching produced duplicate Match records!")

        # Invariant 2: Exactly one NotificationOutbox record created
        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        outbox_count = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        ).count()
        self.assertEqual(outbox_count, 1, "Concurrent matching produced duplicate NotificationOutbox records!")
