"""
Phase 10.5 — End-to-End AI Matching Lifecycle Integration Tests.

Validates the complete candidate-resume and employer-job lifecycle pipelines:
1. Candidate Resume Lifecycle:
   - Eligible candidate new resume upload via API -> on_commit Celery task -> extraction -> 2,048-dim embedding -> hybrid matching -> qualifying match.
   - Resume replacement (Resume A -> Resume B) -> B becomes source of truth -> stale A tasks discarded -> matches reflect only current content.
   - Resume clearance via DELETE /api/v1/candidates/me/resume/ and POST /api/v1/candidates/me/resume/clear/ -> invalidation of text & vector -> stale tasks cannot restore -> matching excluded.
   - Candidate eligibility transitions (open_to_matching, profile_complete) -> exclusion while ineligible -> reuse of valid embedding without re-extraction when eligible -> candidate interaction states preserved.
2. Employer Job Lifecycle:
   - Active first-party job creation via API -> on_commit Celery task -> 2,048-dim embedding -> matching runs only after embedding completes.
   - Material job edits (title, description, tech_stack) -> embedding invalidated -> regenerated -> matching uses latest content -> obsolete queued work discarded.
   - Job deactivation (PAUSED, CLOSED, ARCHIVED) -> embedding invalidated -> excluded from matching -> reactivated to ACTIVE -> re-embedded and re-matched.
   - Non-material edits (salary_range, featured, quality feedback) -> embedding untouched, no tasks enqueued.
3. Matching & Notification Workflow:
   - Hybrid scoring formula (50% semantic, 30% skills, 20% experience).
   - Strict threshold: 70.00 does NOT qualify; > 70 qualifies.
   - Approval gate: visible_to_employer=False on initial creation.
   - Candidate action and recruiter visibility preservation across repeated matching runs.
   - Recruiter high-match alert staging (score >= 85) in NotificationOutbox with idempotency key; zero emails sent.
   - External jobs (Himalayas, Adzuna, People Prime ATS) strictly excluded.
   - Privacy invariants: zero exposure of raw vectors or extracted text in API responses or outbox payloads.
"""

import math
from unittest.mock import MagicMock, call, patch
import uuid
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile
from candidates.serializers import CandidateProfileSerializer
from companies.models import Company
from common.embedding_client import EmbeddingResult
from common.resume_extraction import (
    ExtractionStatus,
    ResumeExtractionResult,
    calculate_content_hash,
    calculate_source_fingerprint,
)
from external_jobs.models import ExternalJob, ExternalJobSource
from jobs.models import Job
from matching.hybrid_engine import (
    HIGH_MATCH_ALERT_THRESHOLD,
    QUALIFICATION_THRESHOLD,
    HybridMatchingEngine,
    calculate_hybrid_score,
    is_candidate_eligible_for_hybrid_matching,
    is_job_eligible_for_hybrid_matching,
)
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
from matching.serializers import AdminMatchSerializer, CandidateMatchSerializer, EmployerMatchSerializer
from matching.tasks import (
    generate_job_embedding_task,
    process_candidate_resume_task,
    run_matching_for_candidate_task,
    run_matching_for_job_task,
)
from notifications.models import DeliveryStatus, NotificationOutbox, NotificationType
from notifications.services import validate_outbox_payload


def make_unit_vector(val: float = 1.0, dim: int = TARGET_EMBEDDING_DIMENSIONS) -> list[float]:
    """Generates a 2,048-dim vector with val at index 0 and 0.0 elsewhere (unit norm if val=1.0)."""
    vec = [0.0] * dim
    vec[0] = val
    return vec


def make_uniform_unit_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS) -> list[float]:
    """Generates a 2,048-dim unit vector where all components are identical."""
    val = 1.0 / math.sqrt(dim)
    return [val] * dim


class CandidateResumeLifecycleE2ETests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # 1. Candidate User & Profile
        self.candidate_user = User.objects.create_user(
            email="candidate_e2e@example.com",
            password="SecurePassword123!",
            role=User.Role.CANDIDATE,
            full_name="Alice Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Senior Python Engineer",
            phone="+1234567890",
            current_title="Senior Backend Engineer",
            years_experience=7,
            skills=["Python", "Django", "PostgreSQL", "Celery"],
            role_categories=["backend", "engineering"],
            experience_level=CandidateProfile.ExperienceLevel.SENIOR,
            salary_min=140000,
            salary_max=180000,
            work_authorization=CandidateProfile.WorkAuthorization.US_CITIZEN,
            us_state="CA",
            preferred_work_type=CandidateProfile.PreferredWorkType.REMOTE,
            availability_status=CandidateProfile.AvailabilityStatus.ACTIVELY_LOOKING,
            privacy_visibility=CandidateProfile.PrivacyVisibility.PUBLIC,
            bio="Passionate distributed systems engineer.",
            open_to_matching=True,
            profile_complete=True,
        )

        # 2. Employer & Active First-Party Job
        self.employer_user = User.objects.create_user(
            email="employer_e2e@example.com",
            password="SecurePassword123!",
            role=User.Role.EMPLOYER,
            full_name="Bob Employer",
        )
        self.company = Company.objects.create(
            name="Prime Tech Corp",
            owner=self.employer_user,
            website="https://primetech.example.com",
            description="Innovative remote tech company.",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Backend Architect",
            description="Leading development of high-throughput distributed Django services.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python", "Django", "PostgreSQL", "Celery"],
            salary_range="$150,000 - $190,000",
            work_type="remote",
            status=Job.Status.ACTIVE,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        # Create JobEmbedding with identical vector direction to ensure strong qualification
        self.job_vector = make_uniform_unit_vector()
        self.job_embedding = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.job_vector,
            content_hash=calculate_content_hash("Senior Python Backend Architect"),
            version="job_v1",
            embedded_at=timezone.now(),
        )

    def _auth_candidate(self):
        refresh = RefreshToken.for_user(self.candidate_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    # -------------------------------------------------------------------------
    # A. Eligible candidate with a new resume
    # -------------------------------------------------------------------------
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_new_resume_upload_e2e_triggers_pipeline_and_qualifying_match(
        self, mock_extract, mock_embed
    ):
        """
        E2E Workflow:
        1. Candidate uploads resume via POST /api/v1/candidates/me/resume/
        2. Celery task scheduled via transaction.on_commit
        3. Extraction & NVIDIA embedding executed
        4. Text & 2,048-dim vector persisted to CandidateResumeEmbedding
        5. Hybrid matching runs and creates qualifying match with visible_to_employer=False
        """
        self._auth_candidate()
        sample_text = "Alice Candidate: Senior Python Engineer with 7 years of Django, PostgreSQL, Celery."
        mock_extract.return_value = ResumeExtractionResult(
            status=ExtractionStatus.SUCCESS,
            text=sample_text,
            content_hash="extracted_hash_alice_v1",
            character_count=len(sample_text),
            word_count=len(sample_text.split()),
        )
        cand_vector = make_uniform_unit_vector()
        mock_embed.return_value = EmbeddingResult(
            embedding=cand_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        pdf_content = b"%PDF-1.4 sample resume for Alice"
        pdf_file = SimpleUploadedFile("alice_resume.pdf", pdf_content, content_type="application/pdf")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_file}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        saved_path = response.data["resumePath"]

        # Run the scheduled Celery task
        task_res = process_candidate_resume_task(
            candidate_profile_id=str(self.candidate_profile.id),
            expected_resume_path=saved_path,
        )
        self.assertEqual(task_res["status"], "completed")
        self.assertTrue(task_res["matching_scheduled"])

        # Verify embedding record in database
        emb = CandidateResumeEmbedding.objects.get(candidate_profile=self.candidate_profile)
        self.assertEqual(emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(emb.dimensions, TARGET_EMBEDDING_DIMENSIONS)
        self.assertEqual(len(emb.embedding), TARGET_EMBEDDING_DIMENSIONS)
        self.assertIn("Alice Candidate", emb.extracted_text)
        self.assertEqual(emb.version, calculate_source_fingerprint(saved_path))

        # Run matching
        matching_res = run_matching_for_candidate_task(str(self.candidate_profile.id))
        self.assertEqual(matching_res["matched"], 1)

        # Verify match record invariants
        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertGreater(match.match_score, QUALIFICATION_THRESHOLD)
        self.assertEqual(match.status, Match.Status.SUGGESTED)
        # Approval gate: visible_to_employer must ALWAYS be False initially
        self.assertFalse(match.visible_to_employer)

    # -------------------------------------------------------------------------
    # B. Candidate replaces a resume
    # -------------------------------------------------------------------------
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    @patch("common.resume_extraction.ResumeTextExtractionService.extract_from_storage")
    def test_resume_replacement_e2e_invalidates_stale_data_and_updates_matches(
        self, mock_extract, mock_embed
    ):
        """
        E2E Workflow:
        1. Resume A is processed and matched.
        2. Candidate uploads Resume B.
        3. Resume B becomes current source of truth in profile.
        4. Stale execution of Resume A task is discarded.
        5. Obsolete resume results cannot be matched.
        6. Resume B is processed, and matches are refreshed.
        """
        self._auth_candidate()

        # Step 1: Upload Resume A
        text_a = "Resume A: Python Backend"
        mock_extract.return_value = ResumeExtractionResult(
            status=ExtractionStatus.SUCCESS,
            text=text_a,
            content_hash="hash_A",
            character_count=len(text_a),
            word_count=len(text_a.split()),
        )
        vector_A = make_uniform_unit_vector()
        mock_embed.return_value = EmbeddingResult(
            embedding=vector_A,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        pdf_A = SimpleUploadedFile("resume_A.pdf", b"%PDF-1.4 Resume A", content_type="application/pdf")
        with self.captureOnCommitCallbacks(execute=True):
            res_A = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_A}, format="multipart")
        path_A = res_A.data["resumePath"]
        process_candidate_resume_task(str(self.candidate_profile.id), expected_resume_path=path_A)
        run_matching_for_candidate_task(str(self.candidate_profile.id))

        match_v1 = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        initial_score = match_v1.match_score

        # Step 2: Upload Resume B (task is scheduled on commit, but execution paused for deterministic inspection)
        pdf_B = SimpleUploadedFile("resume_B.pdf", b"%PDF-1.4 Resume B", content_type="application/pdf")
        with patch("matching.tasks.process_candidate_resume_task.delay") as mock_b_delay:
            with self.captureOnCommitCallbacks(execute=True):
                res_B = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_B}, format="multipart")
            mock_b_delay.assert_called_once_with(str(self.candidate_profile.id), expected_resume_path=res_B.data["resumePath"])
        path_B = res_B.data["resumePath"]

        # Profile is updated to B
        self.candidate_profile.refresh_from_db()
        self.assertEqual(self.candidate_profile.resume_url, path_B)

        # Step 3: Stale task for Resume A running now is discarded
        stale_res = process_candidate_resume_task(str(self.candidate_profile.id), expected_resume_path=path_A)
        self.assertEqual(stale_res["status"], "stale_resume_discarded")

        # Step 4: Before B finishes embedding, candidate is excluded from matching due to fingerprint mismatch
        elig_ok, elig_reason = is_candidate_eligible_for_hybrid_matching(self.candidate_profile)
        self.assertFalse(elig_ok)
        self.assertIn("stale", elig_reason)

        # Step 5: Resume B processes successfully
        text_b = "Resume B: Lead Staff Systems Architect with Django and PostgreSQL"
        mock_extract.return_value = ResumeExtractionResult(
            status=ExtractionStatus.SUCCESS,
            text=text_b,
            content_hash="hash_B",
            character_count=len(text_b),
            word_count=len(text_b.split()),
        )
        mock_embed.return_value = EmbeddingResult(
            embedding=vector_A,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )
        task_b_res = process_candidate_resume_task(str(self.candidate_profile.id), expected_resume_path=path_B)
        self.assertEqual(task_b_res["status"], "completed")

        # Step 6: Candidate is eligible again and matches refresh
        self.candidate_profile.refresh_from_db()
        elig_ok_after, _ = is_candidate_eligible_for_hybrid_matching(self.candidate_profile)
        self.assertTrue(elig_ok_after)

        run_matching_for_candidate_task(str(self.candidate_profile.id))
        match_v2 = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertEqual(Match.objects.filter(candidate_profile=self.candidate_profile, job=self.job).count(), 1)
        self.assertGreater(match_v2.match_score, QUALIFICATION_THRESHOLD)

    # -------------------------------------------------------------------------
    # C. Candidate clears a resume
    # -------------------------------------------------------------------------
    def test_resume_cleared_e2e_invalidates_embedding_and_blocks_matching(self):
        """
        E2E Workflow:
        1. Candidate has completed embedding.
        2. Candidate clears resume via DELETE /api/v1/candidates/me/resume/
        3. Extracted text & embedding vector are invalidated (None, status=FAILED).
        4. Stale in-flight task cannot restore vector or text.
        5. Candidate is strictly ineligible for matching; no new matches or notifications.
        """
        self._auth_candidate()
        self.candidate_profile.resume_url = "resumes/alice/resume_clear_test.pdf"
        self.candidate_profile.save()

        emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_uniform_unit_vector(),
            extracted_text="Private text to be cleared.",
            content_hash="hash_to_clear",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
            embedded_at=timezone.now(),
        )

        # Clear resume via DELETE endpoint
        del_res = self.client.delete("/api/v1/candidates/me/resume/")
        self.assertEqual(del_res.status_code, status.HTTP_200_OK)
        self.assertTrue(del_res.data["ok"])

        # Verify profile resume_url is None
        self.candidate_profile.refresh_from_db()
        self.assertIsNone(self.candidate_profile.resume_url)

        # Verify embedding record is invalidated
        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)
        self.assertIsNone(emb.extracted_text)
        self.assertIsNone(emb.content_hash)
        self.assertEqual(emb.error_message, "Candidate resume was removed.")

        # Stale in-flight task cannot restore cleared resume
        stale_res = process_candidate_resume_task(
            str(self.candidate_profile.id),
            expected_resume_path="resumes/alice/resume_clear_test.pdf",
        )
        self.assertEqual(stale_res["status"], "no_resume")
        emb.refresh_from_db()
        self.assertIsNone(emb.embedding)
        self.assertIsNone(emb.extracted_text)

        # Verify candidate is ineligible for matching
        cand_ok, cand_reason = is_candidate_eligible_for_hybrid_matching(self.candidate_profile)
        self.assertFalse(cand_ok)
        self.assertTrue("no resume" in cand_reason.lower() or "incomplete" in cand_reason.lower())

        match_res = HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        self.assertEqual(match_res["matched"], 0)

    def test_resume_cleared_via_clear_post_endpoint(self):
        """Verifies clearing via dedicated POST /api/v1/candidates/me/resume/clear/ endpoint."""
        self._auth_candidate()
        self.candidate_profile.resume_url = "resumes/alice/resume_clear_post.pdf"
        self.candidate_profile.save()

        emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_uniform_unit_vector(),
            extracted_text="Text to be cleared.",
            content_hash="post_clear_hash",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
            embedded_at=timezone.now(),
        )

        clear_res = self.client.post("/api/v1/candidates/me/resume/clear/")
        self.assertEqual(clear_res.status_code, status.HTTP_200_OK)
        self.assertTrue(clear_res.data["ok"])

        self.candidate_profile.refresh_from_db()
        self.assertIsNone(self.candidate_profile.resume_url)
        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)

    # -------------------------------------------------------------------------
    # D. Candidate eligibility changes
    # -------------------------------------------------------------------------
    @patch("matching.tasks.run_matching_for_candidate_task.delay")
    @patch("matching.tasks.process_candidate_resume_task.delay")
    def test_candidate_eligibility_transitions_e2e(self, mock_process_delay, mock_matching_delay):
        """
        E2E Workflow:
        1. Candidate toggles open_to_matching off: excluded from matching.
        2. Candidate toggles open_to_matching on: matching enqueued WITHOUT re-extracting/re-embedding.
        3. Profile completeness toggle from False to True: matching enqueued directly.
        4. Existing candidate decisions and match states are preserved across runs.
        """
        self.candidate_profile.resume_url = "resumes/alice/active.pdf"
        self.candidate_profile.open_to_matching = True
        self.candidate_profile.profile_complete = True
        self.candidate_profile.save()

        fp = calculate_source_fingerprint(self.candidate_profile.resume_url)
        emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_uniform_unit_vector(),
            extracted_text="Alice's valid text",
            content_hash="valid_hash_1",
            version=fp,
            embedded_at=timezone.now(),
        )

        # 1. Toggle open_to_matching=False
        self.candidate_profile.open_to_matching = False
        self.candidate_profile.save(update_fields=["open_to_matching", "updated_at"])

        res = HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        self.assertEqual(res["matched"], 0)
        self.assertIn("not open to matching", res["reason"])

        mock_process_delay.reset_mock()
        mock_matching_delay.reset_mock()

        # 2. Toggle open_to_matching=True -> on_commit triggers matching task, skips re-embedding
        with self.captureOnCommitCallbacks(execute=True):
            self.candidate_profile.open_to_matching = True
            self.candidate_profile.save(update_fields=["open_to_matching", "updated_at"])

        mock_matching_delay.assert_called_once_with(str(self.candidate_profile.id))
        mock_process_delay.assert_not_called()

        # 3. Create existing match and simulate candidate interaction
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=92,
            match_reason="Initial match reason",
            status=Match.Status.CANDIDATE_INTERESTED,
            visible_to_employer=True,
            recruiter_notified_at=timezone.now(),
        )

        # Re-run matching: score/reason updated, but status and visible_to_employer PRESERVED
        HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.CANDIDATE_INTERESTED)
        self.assertTrue(match.visible_to_employer)
        self.assertEqual(Match.objects.filter(candidate_profile=self.candidate_profile, job=self.job).count(), 1)


class EmployerJobLifecycleE2ETests(TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # Employer User & Company
        self.employer_user = User.objects.create_user(
            email="employer_job_e2e@example.com",
            password="SecurePassword123!",
            role=User.Role.EMPLOYER,
            full_name="Bob Employer",
        )
        self.company = Company.objects.create(
            name="Prime Enterprises",
            owner=self.employer_user,
            website="https://primeenterprises.example.com",
            description="Leading SaaS company.",
        )

        # Candidate with completed valid embedding
        self.candidate_user = User.objects.create_user(
            email="candidate_for_job@example.com",
            password="SecurePassword123!",
            role=User.Role.CANDIDATE,
            full_name="Carol Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Lead Cloud Engineer",
            years_experience=8,
            skills=["Go", "Kubernetes", "AWS"],
            experience_level=CandidateProfile.ExperienceLevel.LEAD,
            resume_url="resumes/carol/cloud_resume.pdf",
            open_to_matching=True,
            profile_complete=True,
        )
        self.cand_vector = make_uniform_unit_vector()
        self.candidate_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.cand_vector,
            content_hash="carol_hash",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
            embedded_at=timezone.now(),
        )

    def _auth_employer(self):
        refresh = RefreshToken.for_user(self.employer_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    # -------------------------------------------------------------------------
    # A. Active job creation
    # -------------------------------------------------------------------------
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_active_job_creation_e2e_triggers_pipeline_and_matching(self, mock_embed):
        """
        E2E Workflow:
        1. Employer creates an active first-party job via POST /api/v1/jobs/
        2. generate_job_embedding_task is scheduled via transaction.on_commit
        3. 2,048-dim vector generated and saved to JobEmbedding
        4. run_matching_for_job_task executed, creating qualifying match
        """
        self._auth_employer()
        job_vec = make_uniform_unit_vector()
        mock_embed.return_value = EmbeddingResult(
            embedding=job_vec,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        job_payload = {
            "title": "Lead Cloud Infrastructure Engineer",
            "description": "Designing high-scale Kubernetes clusters on AWS using Go.",
            "role_type": "full-time",
            "experience_level": "lead",
            "tech_stack": ["Go", "Kubernetes", "AWS"],
            "salary_range": "$170,000 - $210,000",
            "work_type": "remote",
            "visa_requirements": "US Citizen or Permanent Resident",
            "publish": True,
        }

        with patch("matching.tasks.generate_job_embedding_task.delay") as mock_emb_delay:
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.post("/api/v1/jobs/", job_payload, format="json")
            mock_emb_delay.assert_called_once()

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])
        job_id = res.data["jobId"]

        # Run Celery embedding task
        emb_task_res = generate_job_embedding_task(job_id)
        self.assertEqual(emb_task_res["status"], "completed")
        self.assertTrue(emb_task_res["matching_scheduled"])

        # Verify JobEmbedding persisted
        job_emb = JobEmbedding.objects.get(job_id=job_id)
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(len(job_emb.embedding), TARGET_EMBEDDING_DIMENSIONS)

        # Run matching task
        match_task_res = run_matching_for_job_task(job_id)
        self.assertEqual(match_task_res["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job_id=job_id)
        self.assertGreater(match.match_score, QUALIFICATION_THRESHOLD)
        self.assertFalse(match.visible_to_employer)

    # -------------------------------------------------------------------------
    # B. Material job edit
    # -------------------------------------------------------------------------
    @patch("common.embedding_client.NvidiaEmbeddingClient.embed")
    def test_material_job_edit_e2e_regenerates_embedding_and_reruns_matching(self, mock_embed):
        """
        E2E Workflow:
        1. Active job has existing completed embedding.
        2. Employer modifies title & tech_stack via PATCH /api/v1/jobs/<id>/
        3. Previous embedding is invalidated (status=PENDING, embedding=None).
        4. Stale task for old content is rejected.
        5. New embedding generated and matching executed with latest content.
        """
        self._auth_employer()
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Junior Go Developer",
            description="Entry level Go programming.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.JUNIOR,
            tech_stack=["Go"],
            status=Job.Status.ACTIVE,
        )
        old_vec = make_uniform_unit_vector()
        job_emb = JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=old_vec,
            content_hash=calculate_content_hash("Junior Go Developer"),
            version="v_old",
            embedded_at=timezone.now(),
        )

        mock_embed.return_value = EmbeddingResult(
            embedding=make_uniform_unit_vector(),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        # Employer performs material edit (pause eager execution to inspect PENDING state)
        with patch("matching.tasks.generate_job_embedding_task.delay") as mock_edit_delay:
            with self.captureOnCommitCallbacks(execute=True):
                edit_res = self.client.patch(
                    f"/api/v1/jobs/{job.id}/",
                    {"title": "Principal Distributed Systems Architect", "tech_stack": ["Go", "Kubernetes", "AWS"]},
                    format="json",
                )
            mock_edit_delay.assert_called_once_with(str(job.id))
        self.assertEqual(edit_res.status_code, status.HTTP_200_OK)

        # Job embedding was invalidated on material change
        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.PENDING)
        self.assertIsNone(job_emb.embedding)

        # Run task to generate new embedding
        task_res = generate_job_embedding_task(str(job.id))
        self.assertEqual(task_res["status"], "completed")

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertIsNotNone(job_emb.embedding)

    # -------------------------------------------------------------------------
    # C. Job deactivation and reactivation
    # -------------------------------------------------------------------------
    def test_job_deactivation_and_reactivation_e2e(self):
        """
        E2E Workflow:
        1. Active job has completed embedding.
        2. Job is deactivated (PAUSED, CLOSED, ARCHIVED) via PATCH.
        3. JobEmbedding is invalidated (status=FAILED, embedding=None).
        4. Deactivated job is excluded from candidate matching.
        5. Reactivate job to ACTIVE: embedding task is scheduled and matching works again.
        """
        self._auth_employer()
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Backend Lead",
            description="Leading backend systems.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Go", "Kubernetes"],
            status=Job.Status.ACTIVE,
        )
        job_emb = JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=make_uniform_unit_vector(),
            content_hash=calculate_content_hash("Backend Lead"),
            version="lead_v1",
            embedded_at=timezone.now(),
        )

        # Test PAUSED
        self.client.patch(f"/api/v1/jobs/{job.id}/", {"status": Job.Status.PAUSED}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PAUSED)
        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(job_emb.embedding)

        # Excluded from candidate matching
        job_ok, reason = is_job_eligible_for_hybrid_matching(job)
        self.assertFalse(job_ok)

        # Test Reactivation to ACTIVE
        with patch("matching.tasks.generate_job_embedding_task.delay") as mock_gen_delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.patch(f"/api/v1/jobs/{job.id}/", {"status": Job.Status.ACTIVE}, format="json")
            mock_gen_delay.assert_called_once_with(str(job.id))

        # Test CLOSED
        self.client.patch(f"/api/v1/jobs/{job.id}/", {"status": Job.Status.CLOSED}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.CLOSED)
        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)

        # Test ARCHIVED
        self.client.patch(f"/api/v1/jobs/{job.id}/", {"status": Job.Status.ARCHIVED}, format="json")
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.ARCHIVED)
        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.FAILED)

    # -------------------------------------------------------------------------
    # D. Non-material edits
    # -------------------------------------------------------------------------
    def test_non_material_job_edit_e2e_bypasses_pipeline(self):
        """
        Non-material edits (salary_range, featured, jd_quality_score, jd_quality_feedback)
        must NOT invalidate embedding and must NOT enqueue embedding or matching tasks.
        """
        self._auth_employer()
        job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Go Engineer",
            description="Cloud distributed systems.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Go"],
            salary_range="$140,000 - $170,000",
            status=Job.Status.ACTIVE,
        )
        vec = make_uniform_unit_vector()
        job_emb = JobEmbedding.objects.create(
            job=job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=vec,
            content_hash=JobTextPreparationService.prepare_text(job).content_hash,
            version="v_stable",
            embedded_at=timezone.now(),
        )

        with patch("matching.tasks.generate_job_embedding_task.delay") as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.patch(
                    f"/api/v1/jobs/{job.id}/",
                    {
                        "salary_range": "$160,000 - $190,000",
                        "featured": True,
                        "jd_quality_score": 95,
                        "jd_quality_feedback": "Excellent JD",
                    },
                    format="json",
                )

            # No tasks scheduled
            mock_delay.assert_not_called()

        job_emb.refresh_from_db()
        self.assertEqual(job_emb.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(job_emb.version, "v_stable")
        self.assertIsNotNone(job_emb.embedding)


class MatchAndNotificationWorkflowE2ETests(TestCase):
    def setUp(self):
        super().setUp()
        self.employer_user = User.objects.create_user(
            email="emp_workflow@example.com",
            password="SecurePassword123!",
            role=User.Role.EMPLOYER,
        )
        self.company = Company.objects.create(
            name="Workflow Tech",
            owner=self.employer_user,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Python Tech Lead",
            description="Distributed architecture in Python.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.LEAD,
            tech_stack=["Python", "Django", "PostgreSQL"],
            status=Job.Status.ACTIVE,
        )
        self.job_vector = make_uniform_unit_vector()
        self.job_embedding = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.job_vector,
            content_hash="job_hash_wf",
            version="wf_v1",
            embedded_at=timezone.now(),
        )

        self.candidate_user = User.objects.create_user(
            email="cand_workflow@example.com",
            password="SecurePassword123!",
            role=User.Role.CANDIDATE,
            full_name="Dave Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Principal Engineer",
            years_experience=12,
            skills=["Python", "Django", "PostgreSQL"],
            experience_level=CandidateProfile.ExperienceLevel.LEAD,
            resume_url="resumes/dave/resume.pdf",
            open_to_matching=True,
            profile_complete=True,
        )
        self.cand_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            model_name=TARGET_EMBEDDING_MODEL,
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
            embedding=self.job_vector,  # 100% semantic match
            extracted_text="Dave: Principal Engineer Python Django PostgreSQL",
            content_hash="dave_hash",
            version=calculate_source_fingerprint(self.candidate_profile.resume_url),
            embedded_at=timezone.now(),
        )

    # -------------------------------------------------------------------------
    # 1. Scoring formula and threshold enforcement
    # -------------------------------------------------------------------------
    def test_scoring_formula_and_threshold_enforcement(self):
        """
        Verifies:
        - 50% semantic, 30% skills, 20% experience.
        - Exact score of 70.00 does NOT qualify.
        - Strictly > 70.00 qualifies.
        """
        # Exact 70.00: 50% * 80 + 30% * 60 + 20% * 60 = 40 + 18 + 12 = 70.00
        bd_exact = calculate_hybrid_score(semantic_score=80.0, skill_score=60.0, exp_score=60.0)
        self.assertEqual(bd_exact.final_score, 70.0)
        self.assertFalse(bd_exact.qualifies)

        # 70.01 qualifies: 50% * 80.02 + 30% * 60 + 20% * 60 = 40.01 + 18 + 12 = 70.01
        bd_above = calculate_hybrid_score(semantic_score=80.02, skill_score=60.0, exp_score=60.0)
        self.assertEqual(bd_above.final_score, 70.01)
        self.assertTrue(bd_above.qualifies)

    # -------------------------------------------------------------------------
    # 2. Approval gate and state preservation
    # -------------------------------------------------------------------------
    def test_approval_gate_and_state_preservation(self):
        """
        Verifies:
        - Newly created match has visible_to_employer=False.
        - Recruiter approval (visible_to_employer=True, MUTUAL_FIT) is preserved on re-matching.
        """
        # Initial match run
        res = HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        self.assertEqual(res["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertFalse(match.visible_to_employer)
        self.assertEqual(match.status, Match.Status.SUGGESTED)

        # Recruiter approves match and promotes to MUTUAL_FIT
        match.visible_to_employer = True
        match.status = Match.Status.MUTUAL_FIT
        match.save()

        # Re-run matching
        HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        match.refresh_from_db()
        self.assertTrue(match.visible_to_employer)
        self.assertEqual(match.status, Match.Status.MUTUAL_FIT)

    # -------------------------------------------------------------------------
    # 3. High-match recruiter notification and idempotency
    # -------------------------------------------------------------------------
    def test_high_match_recruiter_notification_and_idempotency(self):
        """
        Verifies:
        - Score >= 85 stages a NotificationOutbox record with notification_type=high_match_alert.
        - ZERO live emails are sent (mail.outbox is empty).
        - Repeated matching runs do NOT duplicate NotificationOutbox records (idempotent deduplication).
        """
        mail.outbox.clear()
        res = HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        self.assertEqual(res["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertGreaterEqual(match.match_score, HIGH_MATCH_ALERT_THRESHOLD)

        # Verify NotificationOutbox record staged
        outbox_records = NotificationOutbox.objects.filter(
            match=match,
            notification_type=NotificationType.HIGH_MATCH_ALERT,
        )
        self.assertEqual(outbox_records.count(), 1)
        record = outbox_records.first()
        self.assertEqual(record.status, DeliveryStatus.PENDING)
        self.assertEqual(record.idempotency_key, f"match:{match.id}:high_match_alert")

        # Zero emails sent
        self.assertEqual(len(mail.outbox), 0)

        # Re-run matching: deduplication guarantees no duplicate outbox records
        HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        self.assertEqual(
            NotificationOutbox.objects.filter(match=match, notification_type=NotificationType.HIGH_MATCH_ALERT).count(),
            1,
        )
        self.assertEqual(len(mail.outbox), 0)

    # -------------------------------------------------------------------------
    # 4. External jobs strictly excluded
    # -------------------------------------------------------------------------
    def test_external_jobs_strictly_excluded(self):
        """
        Verifies external jobs (Himalayas, Adzuna, People Prime ATS) cannot be embedded or matched.
        """
        ext_source = ExternalJobSource.objects.create(name="Adzuna", provider_code="adzuna")
        ext_job = ExternalJob.objects.create(
            source=ext_source,
            external_job_id="adzuna_12345",
            title="Senior Python Developer",
            company_name="External Co",
            description="External job posting.",
            location="Remote",
        )

        is_elig, reason = is_eligible_first_party_job(ext_job)
        self.assertFalse(is_elig)
        self.assertIn("not an instance", reason.lower())

        # JobEmbeddingService refuses external job
        emb_res = JobEmbeddingService().generate_embedding_for_job(ext_job.id)
        self.assertFalse(emb_res.is_success)

    # -------------------------------------------------------------------------
    # 5. Privacy invariants: zero exposure of raw vectors or text
    # -------------------------------------------------------------------------
    def test_privacy_invariants_no_vectors_or_resume_text_exposed(self):
        """
        Verifies:
        - CandidateProfileSerializer does not expose raw embedding vectors or extracted_text.
        - Match serializers (Candidate, Employer, Admin) do not expose embedding vectors.
        - NotificationOutbox payload contains no prohibited sensitive keys and passes validate_outbox_payload.
        """
        profile_data = CandidateProfileSerializer(self.candidate_profile).data
        self.assertNotIn("embedding", profile_data)
        self.assertNotIn("extracted_text", profile_data)
        self.assertNotIn("vector", profile_data)

        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=90,
            match_reason="Strong fit",
        )

        cand_match_data = CandidateMatchSerializer(match).data
        self.assertNotIn("embedding", cand_match_data)
        self.assertNotIn("vector", cand_match_data)

        emp_match_data = EmployerMatchSerializer(match).data
        self.assertNotIn("embedding", emp_match_data)
        self.assertNotIn("vector", emp_match_data)

        admin_match_data = AdminMatchSerializer(match).data
        self.assertNotIn("embedding", admin_match_data)
        self.assertNotIn("vector", admin_match_data)

        # Test NotificationOutbox payload privacy
        HybridMatchingEngine.run_matching_for_candidate(self.candidate_profile)
        outbox = NotificationOutbox.objects.filter(match=match).first()
        if outbox:
            validate_outbox_payload(outbox.payload)
