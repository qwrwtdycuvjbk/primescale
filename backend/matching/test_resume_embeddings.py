"""
Integration tests for ResumeEmbeddingService and generate_resume_embedding_task.

Strict Safety:
- All NVIDIA API interactions are mocked. Zero live external API calls.
- Runs exclusively on Django test database.
- Verifies idempotency, dimension validation, non-finite vector rejection,
  stale overwrite concurrency prevention, and absolute privacy.
"""

import math
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from candidates.models import CandidateProfile
from candidates.serializers import (
    AdminCandidateListSerializer,
    CandidateProfileSerializer,
    PublicTalentCardSerializer,
)
from common.embedding_client import (
    EmbeddingAuthenticationError,
    EmbeddingDimensionError,
    EmbeddingPermanentError,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingTransientError,
    EmbeddingValidationError,
    NvidiaEmbeddingClient,
)
from common.resume_extraction import (
    ExtractionStatus,
    ResumeExtractionResult,
    ResumeTextExtractionService,
    calculate_content_hash,
    calculate_source_fingerprint,
)
from companies.models import Company
from jobs.models import Job
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    CandidateResumeEmbedding,
    EmbeddingStatus,
    Match,
)
from matching.resume_embeddings import ResumeEmbeddingResult, ResumeEmbeddingService
from matching.serializers import (
    AdminMatchSerializer,
    CandidateMatchSerializer,
    EmployerMatchSerializer,
)
from matching.tasks import generate_resume_embedding_task


def make_dummy_vector(dim: int = TARGET_EMBEDDING_DIMENSIONS, fill: float = 0.05) -> list[float]:
    """Generates a dummy float vector of specified dimension."""
    return [fill] * dim


class ResumeEmbeddingServiceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="candidate_embed@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Embedding Candidate",
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user,
            headline="Lead Cloud Architect",
            current_title="Principal Engineer",
            skills=["Python", "PostgreSQL", "AWS"],
            role_categories=["Engineering"],
            profile_complete=True,
            open_to_matching=True,
            resume_url="resumes/test_candidate/resume.pdf",
        )

        self.resume_text = (
            "Senior Cloud Architect with 12 years of experience designing high-throughput "
            "distributed systems using Python, Django, PostgreSQL, and AWS infrastructure."
        )
        self.content_hash = calculate_content_hash(self.resume_text)

        self.resume_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.profile,
            extracted_text=self.resume_text,
            content_hash=self.content_hash,
            text_length=len(self.resume_text),
            version=calculate_source_fingerprint(self.profile.resume_url),
            status=EmbeddingStatus.PENDING,
        )

        # Mock embedding client
        self.mock_client = MagicMock(spec=NvidiaEmbeddingClient)
        self.mock_client.model = TARGET_EMBEDDING_MODEL
        self.service = ResumeEmbeddingService(client=self.mock_client)

    # ------------------------------------------------------------------------
    # 1. Successful Embedding Generation & Persistence
    # ------------------------------------------------------------------------
    def test_successful_embedding_generation_and_persistence(self):
        """Successfully generates a 2,048-dim vector and persists it with complete metadata."""
        dummy_vector = make_dummy_vector()
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        self.assertTrue(result.is_success)
        self.assertEqual(result.dimensions, 2048)
        self.assertEqual(result.model_name, TARGET_EMBEDDING_MODEL)
        self.assertEqual(result.content_hash, self.content_hash)
        self.assertFalse(result.is_unchanged)
        self.assertFalse(result.is_stale)
        self.assertIsNone(result.error_message)

        # Verify database record
        self.resume_embedding.refresh_from_db()
        self.assertEqual(self.resume_embedding.status, EmbeddingStatus.COMPLETED)
        self.assertIsNotNone(self.resume_embedding.embedding)
        self.assertEqual(len(self.resume_embedding.embedding), 2048)
        self.assertEqual(list(self.resume_embedding.embedding), dummy_vector)
        self.assertEqual(self.resume_embedding.dimensions, 2048)
        self.assertEqual(self.resume_embedding.model_name, TARGET_EMBEDDING_MODEL)
        self.assertEqual(self.resume_embedding.content_hash, self.content_hash)
        self.assertEqual(self.resume_embedding.text_length, len(self.resume_text))
        self.assertIsNotNone(self.resume_embedding.embedded_at)
        self.assertIsNone(self.resume_embedding.error_message)

    def test_correct_passage_input_type_and_model_configuration(self):
        """Verifies input_type='passage' is passed to the NVIDIA client."""
        dummy_vector = make_dummy_vector()
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=dummy_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        self.service.generate_embedding_for_candidate(self.profile)

        self.mock_client.embed.assert_called_once_with(
            text=self.resume_text[:16_000],
            input_type="passage",
        )

    # ------------------------------------------------------------------------
    # 2. Vector Validation & Non-Finite Value Rejection
    # ------------------------------------------------------------------------
    def test_wrong_vector_dimension_rejection(self):
        """Rejects vector with dimension other than 2,048 (e.g. 1,024) and marks status FAILED."""
        short_vector = make_dummy_vector(dim=1024)
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=short_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=1024,
        )

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertFalse(result.is_success)
        self.assertIn("dimensions", result.error_message.lower())

        self.resume_embedding.refresh_from_db()
        self.assertEqual(self.resume_embedding.status, EmbeddingStatus.FAILED)
        self.assertIsNone(self.resume_embedding.embedding)

    def test_non_finite_vector_nan_rejection(self):
        """Rejects vector containing NaN values and marks status FAILED."""
        nan_vector = make_dummy_vector()
        nan_vector[42] = float("nan")
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=nan_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertFalse(result.is_success)
        self.assertIn("non-finite", result.error_message.lower())

        self.resume_embedding.refresh_from_db()
        self.assertEqual(self.resume_embedding.status, EmbeddingStatus.FAILED)
        self.assertIsNone(self.resume_embedding.embedding)

    def test_non_finite_vector_inf_rejection(self):
        """Rejects vector containing positive/negative Infinity and marks status FAILED."""
        inf_vector = make_dummy_vector()
        inf_vector[100] = float("inf")
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=inf_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=2048,
        )

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("non-finite", result.error_message.lower())

    # ------------------------------------------------------------------------
    # 3. Missing, Empty, or Failed Extracted Text Handling
    # ------------------------------------------------------------------------
    def test_empty_or_whitespace_extracted_text_rejected(self):
        """Rejects empty or whitespace-only extracted text without invoking embedding API."""
        self.resume_embedding.extracted_text = "   \n\t   "
        self.resume_embedding.save(update_fields=["extracted_text"])

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("no extracted resume text", result.error_message.lower())
        self.mock_client.embed.assert_not_called()

    def test_none_extracted_text_rejected(self):
        """Rejects missing (None) extracted text without invoking embedding API."""
        self.resume_embedding.extracted_text = None
        self.resume_embedding.save(update_fields=["extracted_text"])

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.mock_client.embed.assert_not_called()

    def test_extraction_failed_status_rejected(self):
        """Rejects candidate whose extraction status is marked FAILED."""
        self.resume_embedding.status = EmbeddingStatus.FAILED
        self.resume_embedding.extracted_text = ""
        self.resume_embedding.error_message = "Corrupt PDF stream"
        self.resume_embedding.save(update_fields=["status", "extracted_text", "error_message"])

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.mock_client.embed.assert_not_called()

    def test_nonexistent_candidate_profile_rejected(self):
        """Handles nonexistent candidate profile UUID safely."""
        fake_id = str(uuid.uuid4())
        result = self.service.generate_embedding_for_candidate(fake_id)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("does not exist", result.error_message)

    # ------------------------------------------------------------------------
    # 4. Idempotency & Unchanged Content Hash
    # ------------------------------------------------------------------------
    def test_unchanged_content_hash_avoids_redundant_call(self):
        """Skips API call if embedding is already completed with identical content hash."""
        dummy_vector = make_dummy_vector()
        self.resume_embedding.embedding = dummy_vector
        self.resume_embedding.status = EmbeddingStatus.COMPLETED
        self.resume_embedding.embedded_at = timezone.now()
        self.resume_embedding.save(update_fields=["embedding", "status", "embedded_at"])

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        self.assertTrue(result.is_unchanged)
        self.mock_client.embed.assert_not_called()

    def test_force_regenerate_bypasses_unchanged_check(self):
        """Force regenerate flag calls API even if content hash matches completed embedding."""
        dummy_vector = make_dummy_vector()
        self.resume_embedding.embedding = dummy_vector
        self.resume_embedding.status = EmbeddingStatus.COMPLETED
        self.resume_embedding.embedded_at = timezone.now()
        self.resume_embedding.save(update_fields=["embedding", "status", "embedded_at"])

        new_vector = make_dummy_vector(fill=0.99)
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=new_vector,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        result = self.service.generate_embedding_for_candidate(self.profile, force_regenerate=True)

        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        self.assertFalse(result.is_unchanged)
        self.mock_client.embed.assert_called_once()

    # ------------------------------------------------------------------------
    # 5. Resume Update & Stale Overwrite Concurrency Protection
    # ------------------------------------------------------------------------
    def test_updated_resume_content_invalidates_stale_embedding(self):
        """When candidate uploads new resume with different text/hash, generates new embedding."""
        # 1. First completed embedding
        v1 = make_dummy_vector(fill=0.1)
        self.resume_embedding.embedding = v1
        self.resume_embedding.status = EmbeddingStatus.COMPLETED
        self.resume_embedding.save()

        # 2. Candidate updates resume text
        new_text = "Updated Resume Text: Senior Staff AI Infrastructure Engineer at Scale."
        new_hash = calculate_content_hash(new_text)
        self.resume_embedding.extracted_text = new_text
        self.resume_embedding.content_hash = new_hash
        self.resume_embedding.status = EmbeddingStatus.PENDING
        self.resume_embedding.save()

        # 3. Embedding generation runs for updated text
        v2 = make_dummy_vector(fill=0.88)
        self.mock_client.embed.return_value = EmbeddingResult(
            embedding=v2,
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.COMPLETED)
        self.assertEqual(result.content_hash, new_hash)
        self.resume_embedding.refresh_from_db()
        self.assertEqual(list(self.resume_embedding.embedding), v2)
        self.assertEqual(self.resume_embedding.content_hash, new_hash)

    def test_concurrent_resume_update_discards_stale_vector(self):
        """If resume text updates concurrently during API call, discards stale vector without overwriting."""
        # Setup: side_effect simulates concurrent DB update while client.embed is in flight
        def simulate_concurrent_upload(*args, **kwargs):
            # Concurrent process updates the resume text and hash
            newer_text = "Brand New Resume uploaded 100ms ago by candidate!"
            newer_hash = calculate_content_hash(newer_text)
            CandidateResumeEmbedding.objects.filter(id=self.resume_embedding.id).update(
                extracted_text=newer_text,
                content_hash=newer_hash,
                status=EmbeddingStatus.PENDING,
            )
            # Return vector for the OLD text
            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.01),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_concurrent_upload

        result = self.service.generate_embedding_for_candidate(self.profile)

        # Stale result must be detected and discarded
        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message.lower())

        # DB must still have the NEWER text and NO stale vector attached to it
        self.resume_embedding.refresh_from_db()
        self.assertIn("Brand New Resume", self.resume_embedding.extracted_text)
        self.assertIsNone(self.resume_embedding.embedding)

    def test_new_upload_before_extraction_detected_as_out_of_sync(self):
        """
        When candidate uploads a new resume file, profile.resume_url changes immediately.
        Before extraction runs, generate_embedding_for_candidate detects the version mismatch
        and safely aborts without generating an embedding for stale text.
        """
        self.resume_embedding.version = calculate_source_fingerprint(self.profile.resume_url)
        self.resume_embedding.save(update_fields=["version"])

        # Candidate uploads new resume file; profile.resume_url updates immediately
        self.profile.resume_url = "resumes/test_candidate/newly_uploaded_resume.pdf"
        self.profile.save(update_fields=["resume_url"])

        # Task or service called before extraction has updated resume_embedding
        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertTrue(result.is_stale)
        self.assertIn("out of sync", result.error_message.lower())
        self.mock_client.embed.assert_not_called()

    def test_upload_in_flight_discards_stale_embedding_even_before_extraction(self):
        """
        If a candidate uploads a new resume while embedding generation is in flight,
        profile.resume_url changes even before extraction updates content_hash/text.
        The commit block detects the resume_url change, marks is_stale=True, and
        discards the vector without attaching it to the profile.
        """
        self.resume_embedding.version = calculate_source_fingerprint(self.profile.resume_url)
        self.resume_embedding.save(update_fields=["version"])

        def simulate_upload_during_api_call(*args, **kwargs):
            CandidateProfile.objects.filter(id=self.profile.id).update(
                resume_url="resumes/test_candidate/concurrent_upload.pdf"
            )
            return EmbeddingResult(
                embedding=make_dummy_vector(fill=0.77),
                model=TARGET_EMBEDDING_MODEL,
                input_type="passage",
                dimensions=TARGET_EMBEDDING_DIMENSIONS,
            )

        self.mock_client.embed.side_effect = simulate_upload_during_api_call

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertTrue(result.is_stale)
        self.assertIn("concurrently", result.error_message.lower())

        self.resume_embedding.refresh_from_db()
        self.assertIsNone(self.resume_embedding.embedding)
        self.assertNotEqual(self.resume_embedding.status, EmbeddingStatus.COMPLETED)

    def test_failed_extraction_invalidates_previous_vector_and_metadata(self):
        """
        When extraction for a newly uploaded resume fails, any previously existing
        vector, hash, and text must be wiped so stale vectors cannot be used for matching.
        """
        self.resume_embedding.embedding = make_dummy_vector(fill=0.12)
        self.resume_embedding.status = EmbeddingStatus.COMPLETED
        self.resume_embedding.embedded_at = timezone.now()
        self.resume_embedding.version = calculate_source_fingerprint(self.profile.resume_url)
        self.resume_embedding.save()

        self.profile.resume_url = "resumes/test_candidate/corrupted_file.pdf"
        self.profile.save(update_fields=["resume_url"])

        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage.size.return_value = 1000
        mock_storage.open.side_effect = Exception("Storage read error")
        extractor = ResumeTextExtractionService(storage=mock_storage)

        extract_result = extractor.extract_and_persist_for_candidate(self.profile)

        self.assertFalse(extract_result.is_success)
        self.resume_embedding.refresh_from_db()
        self.assertEqual(self.resume_embedding.status, EmbeddingStatus.FAILED)
        self.assertIsNone(self.resume_embedding.embedding)
        self.assertIsNone(self.resume_embedding.embedded_at)
        self.assertIsNone(self.resume_embedding.extracted_text)
        self.assertIsNone(self.resume_embedding.content_hash)
        self.assertEqual(self.resume_embedding.text_length, 0)
        self.assertEqual(
            self.resume_embedding.version,
            calculate_source_fingerprint("resumes/test_candidate/corrupted_file.pdf"),
        )

        eligible = CandidateResumeEmbedding.objects.filter(
            candidate_profile=self.profile,
            status=EmbeddingStatus.COMPLETED,
            embedding__isnull=False,
        ).exists()
        self.assertFalse(eligible)


    # ------------------------------------------------------------------------
    # 6. Retryable vs Permanent Error Handling
    # ------------------------------------------------------------------------
    def test_permanent_authentication_error_marks_failed(self):
        """Permanent auth error (HTTP 401/403) marks record FAILED without retry."""
        self.mock_client.embed.side_effect = EmbeddingAuthenticationError("Invalid API key")

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("EmbeddingAuthenticationError", result.error_message)

        self.resume_embedding.refresh_from_db()
        self.assertEqual(self.resume_embedding.status, EmbeddingStatus.FAILED)
        self.assertIn("EmbeddingAuthenticationError", self.resume_embedding.error_message)

    def test_permanent_validation_error_marks_failed(self):
        """Permanent validation error (HTTP 400/422) marks record FAILED."""
        self.mock_client.embed.side_effect = EmbeddingPermanentError("HTTP 422 Unprocessable")

        result = self.service.generate_embedding_for_candidate(self.profile)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("EmbeddingPermanentError", result.error_message)

    def test_transient_error_reraises_when_raise_on_transient_is_true(self):
        """Transient error re-raises when raise_on_transient=True so Celery can handle retries."""
        self.mock_client.embed.side_effect = EmbeddingTransientError("Connection reset")

        with self.assertRaises(EmbeddingTransientError):
            self.service.generate_embedding_for_candidate(self.profile, raise_on_transient=True)

    def test_transient_error_returns_failure_when_raise_on_transient_is_false(self):
        """Transient error returns failure without crashing when raise_on_transient=False."""
        self.mock_client.embed.side_effect = EmbeddingTransientError("Connection reset")

        result = self.service.generate_embedding_for_candidate(self.profile, raise_on_transient=False)

        self.assertEqual(result.status, EmbeddingStatus.FAILED)
        self.assertIn("Transient", result.error_message)


class ResumeEmbeddingTaskTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="candidate_task@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Task Candidate",
        )
        self.profile = CandidateProfile.objects.create(
            user=self.user,
            headline="DevOps Lead",
            current_title="Infrastructure Architect",
            skills=["Kubernetes", "Terraform", "Python"],
            role_categories=["Engineering"],
            profile_complete=True,
            open_to_matching=True,
            resume_url="resumes/test_task/resume.pdf",
        )
        self.resume_text = "Experienced Infrastructure Architect with Kubernetes and Terraform expertise."
        self.content_hash = calculate_content_hash(self.resume_text)

        self.resume_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.profile,
            extracted_text=self.resume_text,
            content_hash=self.content_hash,
            text_length=len(self.resume_text),
            status=EmbeddingStatus.PENDING,
        )

    # ------------------------------------------------------------------------
    # 7. Celery Task Execution & Idempotency
    # ------------------------------------------------------------------------
    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    def test_idempotent_celery_task_execution(self, mock_client_cls):
        """Celery task executes idempotently and returns sanitized summary without leaking text/vectors."""
        mock_instance = MagicMock()
        mock_instance.model = TARGET_EMBEDDING_MODEL
        mock_instance.embed.return_value = EmbeddingResult(
            embedding=make_dummy_vector(),
            model=TARGET_EMBEDDING_MODEL,
            input_type="passage",
            dimensions=TARGET_EMBEDDING_DIMENSIONS,
        )
        mock_client_cls.return_value = mock_instance

        # 1. First execution generates embedding
        res1 = generate_resume_embedding_task(str(self.profile.id))
        self.assertEqual(res1["status"], "completed")
        self.assertFalse(res1["is_unchanged"])
        self.assertEqual(res1["dimensions"], 2048)
        self.assertNotIn("extracted_text", res1)
        self.assertNotIn("embedding", res1)

        # 2. Second execution recognizes unchanged content
        res2 = generate_resume_embedding_task(str(self.profile.id))
        self.assertEqual(res2["status"], "completed")
        self.assertTrue(res2["is_unchanged"])
        # Client only invoked once!
        self.assertEqual(mock_instance.embed.call_count, 1)

    @patch("matching.resume_embeddings.NvidiaEmbeddingClient")
    def test_celery_task_permanent_error_returns_failed_without_retry(self, mock_client_cls):
        """Permanent error returns failed dictionary without crashing or infinite retries."""
        mock_instance = MagicMock()
        mock_instance.model = TARGET_EMBEDDING_MODEL
        mock_instance.embed.side_effect = EmbeddingAuthenticationError("Bad Key")
        mock_client_cls.return_value = mock_instance

        res = generate_resume_embedding_task(str(self.profile.id))
        self.assertEqual(res["status"], "failed")
        self.assertIn("EmbeddingAuthenticationError", res["error"])

    # ------------------------------------------------------------------------
    # 8. Absolute Privacy: No Vectors or Private Text in Serializers
    # ------------------------------------------------------------------------
    def test_embedding_and_text_never_exposed_in_any_serializer(self):
        """Verifies that CandidateResumeEmbedding vectors and extracted_text never appear in any API serializer."""
        self.resume_embedding.embedding = make_dummy_vector()
        self.resume_embedding.status = EmbeddingStatus.COMPLETED
        self.resume_embedding.save()

        # Create employer & job & match
        employer_user = User.objects.create_user(
            email="emp_privacy@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Employer User",
        )
        company = Company.objects.create(owner=employer_user, name="TechCorp")
        job = Job.objects.create(
            company=company,
            posted_by=employer_user,
            title="Senior Architect",
            description="Looking for an architect.",
            status=Job.Status.ACTIVE,
        )
        match = Match.objects.create(
            candidate_profile=self.profile,
            job=job,
            match_score=90,
            status=Match.Status.SUGGESTED,
        )

        # 1. CandidateProfileSerializer
        cand_data = CandidateProfileSerializer(self.profile).data
        self.assertNotIn("extracted_text", cand_data)
        self.assertNotIn("embedding", cand_data)
        self.assertNotIn("resume_embedding", cand_data)

        # 2. AdminCandidateListSerializer
        admin_data = AdminCandidateListSerializer(self.profile).data
        self.assertNotIn("extracted_text", admin_data)
        self.assertNotIn("embedding", admin_data)
        self.assertNotIn("resume_embedding", admin_data)

        # 3. PublicTalentCardSerializer
        public_data = PublicTalentCardSerializer(self.profile).data
        self.assertNotIn("extracted_text", public_data)
        self.assertNotIn("embedding", public_data)

        # 4. CandidateMatchSerializer
        cand_match = CandidateMatchSerializer(match).data
        self.assertNotIn("extracted_text", cand_match)
        self.assertNotIn("embedding", cand_match)

        # 5. EmployerMatchSerializer
        emp_match = EmployerMatchSerializer(match).data
        self.assertNotIn("extracted_text", emp_match)
        self.assertNotIn("embedding", emp_match)

        # 6. AdminMatchSerializer
        admin_match = AdminMatchSerializer(match).data
        self.assertNotIn("extracted_text", admin_match)
        self.assertNotIn("embedding", admin_match)
