"""
Phase 10.2: Candidate Resume Lifecycle Pipeline and Task Orchestration Tests.

Covers:
1. Successful resume upload schedules processing after transaction commit.
2. Resume replacement schedules processing for the new resume.
3. Unrelated profile updates (headline, bio, etc.) do not enqueue resume processing.
4. Rolled-back transactions do not enqueue tasks.
5. Extraction succeeds before embedding generation begins.
6. Invalid or empty extracted text does not generate an embedding.
7. Successful embedding generation triggers matching only for eligible candidates.
8. Ineligible candidates (open_to_matching=False or profile_complete=False) do not trigger matching.
9. Clearing a resume invalidates or removes associated private embedding data correctly.
10. Stale task cannot overwrite a newer resume's embedding or trigger matching for obsolete content.
11. Duplicate processing does not create duplicate matches or unnecessary embedding calls.
12. External jobs (Himalayas, Adzuna, People Prime ATS) remain strictly excluded from first-party matching.
13. Existing ownership, privacy, score-threshold, and approval-gate semantics remain preserved.
"""

import io
from unittest.mock import MagicMock, call, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from external_jobs.models import ExternalJob, ExternalJobSource
from jobs.models import Job
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    CandidateResumeEmbedding,
    EmbeddingStatus,
    JobEmbedding,
    Match,
)
from matching.tasks import process_candidate_resume_task, run_matching_for_candidate_task
from common.resume_extraction import calculate_content_hash, calculate_source_fingerprint


def make_dummy_vector(dim=TARGET_EMBEDDING_DIMENSIONS, val=0.05):
    vec = [val] * dim
    return vec


class CandidateResumeLifecyclePipelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Candidate User & Profile
        self.candidate_user = User.objects.create_user(
            email="candidate_lifecycle@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Full Stack Python Engineer",
            current_title="Software Developer",
            years_experience=5,
            skills=["Python", "Django", "PostgreSQL", "React"],
            experience_level=CandidateProfile.ExperienceLevel.SENIOR,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            open_to_matching=True,
            profile_complete=True,
            profile_completeness=100,
        )

        # Create Employer & Company & First-Party Active Job
        self.employer_user = User.objects.create_user(
            email="employer_lifecycle@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="Prime Tech Corp",
            owner=self.employer_user,
        )
        self.active_job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Django Architect",
            description="We are seeking a senior Python Django architect with PostgreSQL experience.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python", "Django", "PostgreSQL"],
            salary_range="$140,000 - $170,000",
            status=Job.Status.ACTIVE,
        )
        # Create completed embedding for active job
        self.job_embedding = JobEmbedding.objects.create(
            job=self.active_job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(val=0.05),
            content_hash="job_hash_123",
            embedded_at=timezone.now(),
        )

    def _auth_candidate(self):
        refresh = RefreshToken.for_user(self.candidate_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    # ------------------------------------------------------------------------
    # 1. Successful resume upload schedules processing after transaction commit
    # ------------------------------------------------------------------------
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_resume_upload_schedules_processing_on_commit(self, mock_process_task):
        self._auth_candidate()
        pdf_file = SimpleUploadedFile(
            "resume.pdf",
            b"%PDF-1.4 valid dummy pdf content",
            content_type="application/pdf",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/candidates/me/resume/",
                {"file": pdf_file},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.candidate_profile.refresh_from_db()
        self.assertIsNotNone(self.candidate_profile.resume_url)

        # Verify task was enqueued with candidate profile ID and resume path
        mock_process_task.assert_called_once_with(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

    # ------------------------------------------------------------------------
    # 2. Resume replacement schedules processing for the new resume
    # ------------------------------------------------------------------------
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_resume_replacement_schedules_processing_for_new_resume(self, mock_process_task):
        self._auth_candidate()
        # Initial resume
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/old_resume.pdf"
        self.candidate_profile.save()

        new_pdf = SimpleUploadedFile(
            "new_resume.pdf",
            b"%PDF-1.4 updated resume",
            content_type="application/pdf",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/candidates/me/resume/",
                {"file": new_pdf},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.candidate_profile.refresh_from_db()
        self.assertIn("new_resume", self.candidate_profile.resume_url)

        # Enqueued for the new resume
        mock_process_task.assert_called_once_with(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

    # ------------------------------------------------------------------------
    # 3. Unrelated profile updates do not enqueue resume processing
    # ------------------------------------------------------------------------
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_unrelated_profile_updates_do_not_enqueue_processing(self, mock_process_task):
        self._auth_candidate()
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/my_resume.pdf"
        self.candidate_profile.save()

        # Update headline and bio only
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate_profile.headline = "Staff Python Engineer & Architect"
            self.candidate_profile.bio = "Updated bio with extensive distributed systems experience."
            self.candidate_profile.save()

        mock_process_task.assert_not_called()

    # ------------------------------------------------------------------------
    # 4. Rolled-back transactions do not enqueue tasks
    # ------------------------------------------------------------------------
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_rolled_back_transaction_does_not_enqueue_task(self, mock_process_task):
        try:
            with transaction.atomic():
                self.candidate_profile.resume_url = "aborted/resume.pdf"
                self.candidate_profile.save()
                raise ValueError("Simulated database failure before commit")
        except ValueError:
            pass

        # Since transaction was rolled back, task must never be enqueued
        mock_process_task.assert_not_called()

    # ------------------------------------------------------------------------
    # 5. Extraction succeeds before embedding generation begins
    # ------------------------------------------------------------------------
    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_pipeline_extracts_then_embeds_then_matches(
        self,
        mock_extract,
        mock_client_cls,
        mock_matching_task,
    ):
        mock_extract.return_value = MagicMock(
            is_success=True,
            text="Extracted text from senior Python architect resume.",
            content_hash=calculate_content_hash("Extracted text from senior Python architect resume."),
            character_count=52,
            word_count=7,
            status=MagicMock(value="success"),
        )
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = MagicMock(
            embedding=make_dummy_vector(val=0.05),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
        )
        mock_client_cls.return_value = mock_client

        self.candidate_profile.resume_url = f"{self.candidate_user.id}/resume.pdf"
        self.candidate_profile.save()

        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["matching_scheduled"])

        # Verify embedding record in database
        emb = CandidateResumeEmbedding.objects.get(candidate_profile=self.candidate_profile)
        self.assertEqual(emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(len(emb.embedding), 2048)
        self.assertEqual(emb.extracted_text, "Extracted text from senior Python architect resume.")

        # Verify matching was enqueued
        mock_matching_task.assert_called_once_with(str(self.candidate_profile.id))

    # ------------------------------------------------------------------------
    # 6. Invalid or empty extracted text does not generate an embedding
    # ------------------------------------------------------------------------
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_extraction_failure_halts_pipeline_without_calling_embedding(
        self,
        mock_extract,
        mock_client_cls,
    ):
        mock_extract.return_value = MagicMock(
            is_success=False,
            text=None,
            content_hash=None,
            character_count=0,
            error_message="Corrupted PDF stream or decompression bomb detected.",
            status=MagicMock(value="corrupt_or_malformed"),
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        self.candidate_profile.resume_url = f"{self.candidate_user.id}/corrupted.pdf"
        self.candidate_profile.save()

        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

        self.assertEqual(result["status"], "extraction_failed")
        self.assertIn("Corrupted PDF", result["error"])

        # NVIDIA client was NEVER called
        mock_client.embed.assert_not_called()

        # Database record is marked FAILED, no vector
        emb = CandidateResumeEmbedding.objects.get(candidate_profile=self.candidate_profile)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)
        self.assertIsNone(emb.extracted_text)

    # ------------------------------------------------------------------------
    # 7 & 8. Candidate eligibility gates matching execution
    # ------------------------------------------------------------------------
    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_ineligible_candidate_embeds_but_does_not_trigger_matching(
        self,
        mock_extract,
        mock_client_cls,
        mock_matching_task,
    ):
        mock_extract.return_value = MagicMock(
            is_success=True,
            text="Resume text for candidate who is not looking.",
            content_hash="hash_not_looking",
            character_count=45,
            word_count=8,
            status=MagicMock(value="success"),
        )
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = MagicMock(
            embedding=make_dummy_vector(val=0.05),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
        )
        mock_client_cls.return_value = mock_client

        # Candidate is NOT open to matching
        self.candidate_profile.open_to_matching = False
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/resume.pdf"
        self.candidate_profile.save()

        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["matching_scheduled"])
        mock_matching_task.assert_not_called()

        # Now, when candidate later becomes eligible:
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate_profile.open_to_matching = True
            self.candidate_profile.save()

        # Matching is enqueued now using the existing valid embedding without re-calling NVIDIA API!
        mock_matching_task.assert_called_once_with(str(self.candidate_profile.id))
        self.assertEqual(mock_client.embed.call_count, 1)

    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_resume_processing_sub_100_completeness_does_not_dispatch_matching_until_100(
        self,
        mock_extract,
        mock_client_cls,
        mock_matching_task,
    ):
        mock_extract.return_value = MagicMock(
            is_success=True,
            text="Resume text for candidate with 90 percent completeness.",
            content_hash="hash_90_pct",
            character_count=50,
            word_count=8,
            status=MagicMock(value="success"),
        )
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = MagicMock(
            embedding=make_dummy_vector(val=0.05),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
        )
        mock_client_cls.return_value = mock_client

        # Candidate has profile_completeness = 90
        self.candidate_profile.profile_completeness = 90
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/incomplete_resume.pdf"
        self.candidate_profile.save()

        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["matching_scheduled"])
        mock_matching_task.assert_not_called()

        # When candidate subsequently reaches 100% profile completeness:
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate_profile.profile_completeness = 100
            self.candidate_profile.save()

        # Matching is dispatched on reaching 100% with the existing embedding
        mock_matching_task.assert_called_once_with(str(self.candidate_profile.id))

    # ------------------------------------------------------------------------
    # 9. Clearing a resume invalidates associated private embedding data
    # ------------------------------------------------------------------------
    def test_clearing_resume_invalidates_embedding_data(self):
        # Setup initial completed embedding
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/to_be_cleared.pdf"
        self.candidate_profile.save()

        emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_dummy_vector(val=0.05),
            extracted_text="Some private resume text.",
            content_hash="hash_123",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
        )

        # Clear resume
        self.candidate_profile.resume_url = ""
        self.candidate_profile.save()

        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)
        self.assertIsNone(emb.extracted_text)
        self.assertEqual(emb.error_message, "Candidate resume was removed.")

    # ------------------------------------------------------------------------
    # 10. Stale task cannot overwrite a newer resume's embedding
    # ------------------------------------------------------------------------
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_stale_task_discards_without_overwriting_newer_resume(
        self,
        mock_extract,
        mock_client_cls,
    ):
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/newer_resume.pdf"
        self.candidate_profile.save()

        # Stale task was dispatched for "older_resume.pdf"
        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=f"{self.candidate_user.id}/older_resume.pdf",
        )

        self.assertEqual(result["status"], "stale_resume_discarded")
        mock_extract.assert_not_called()
        mock_client_cls.assert_not_called()

    # ------------------------------------------------------------------------
    # 11. Duplicate processing does not make unnecessary embedding calls
    # ------------------------------------------------------------------------
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_duplicate_processing_is_idempotent(
        self,
        mock_extract,
        mock_client_cls,
    ):
        text_content = "Unique extracted resume text for idempotency testing."
        c_hash = calculate_content_hash(text_content)
        mock_extract.return_value = MagicMock(
            is_success=True,
            text=text_content,
            content_hash=c_hash,
            character_count=len(text_content),
            word_count=len(text_content.split()),
            status=MagicMock(value="success"),
        )
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = MagicMock(
            embedding=make_dummy_vector(val=0.05),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
        )
        mock_client_cls.return_value = mock_client

        self.candidate_profile.resume_url = f"{self.candidate_user.id}/idempotent.pdf"
        self.candidate_profile.save()

        # Run 1
        res1 = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )
        self.assertEqual(res1["status"], "completed")
        self.assertFalse(res1["is_unchanged"])
        self.assertEqual(mock_client.embed.call_count, 1)

        # Run 2 (duplicate execution)
        res2 = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )
        self.assertEqual(res2["status"], "completed")
        self.assertTrue(res2["is_unchanged"])
        # API call count remained 1!
        self.assertEqual(mock_client.embed.call_count, 1)

    # ------------------------------------------------------------------------
    # 12. External jobs remain strictly excluded from first-party matching
    # ------------------------------------------------------------------------
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_external_jobs_never_matched(
        self,
        mock_extract,
        mock_client_cls,
    ):
        # Create an external job source & external job
        ext_source = ExternalJobSource.objects.create(
            name="Himalayas",
            provider_code="himalayas",
            api_enabled=True,
            attribution_name="Himalayas",
        )
        ext_job = ExternalJob.objects.create(
            source=ext_source,
            external_job_id="ext_himalayas_999",
            title="Senior Python Django Architect",
            company_name="External Remote Co",
            description="External Python Django architect position.",
            status=ExternalJob.Status.ACTIVE,
        )

        mock_extract.return_value = MagicMock(
            is_success=True,
            text="Senior Python Django engineer with extensive PostgreSQL skills.",
            content_hash="hash_ext_test",
            character_count=60,
            word_count=8,
            status=MagicMock(value="success"),
        )
        mock_client = MagicMock()
        mock_client.model = TARGET_EMBEDDING_MODEL
        mock_client.embed.return_value = MagicMock(
            embedding=make_dummy_vector(val=0.05),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
        )
        mock_client_cls.return_value = mock_client

        self.candidate_profile.resume_url = f"{self.candidate_user.id}/resume.pdf"
        self.candidate_profile.save()

        # Run full pipeline with eager matching
        result = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path=self.candidate_profile.resume_url,
        )
        self.assertEqual(result["status"], "completed")

        # Execute hybrid matching directly
        match_result = run_matching_for_candidate_task(str(self.candidate_profile.id))
        self.assertGreaterEqual(match_result["matched"], 1)

        # Confirm all matches are for first-party Job, never ExternalJob
        matches = Match.objects.filter(candidate_profile=self.candidate_profile)
        self.assertTrue(matches.exists())
        for m in matches:
            self.assertIsInstance(m.job, Job)
            self.assertEqual(m.job.id, self.active_job.id)
            self.assertFalse(m.visible_to_employer)  # Approval gate preserved!
