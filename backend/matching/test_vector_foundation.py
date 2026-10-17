import uuid
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User
from candidates.models import CandidateProfile
from candidates.serializers import (
    AdminCandidateListSerializer,
    CandidateProfileSerializer,
    PublicTalentCardSerializer,
)
from companies.models import Company
from jobs.models import Job
from jobs.serializers import (
    EmployerJobPublicSerializer,
    JobPublicListSerializer,
    JobSerializer,
)
from matching.models import (
    CandidateResumeEmbedding,
    EmbeddingStatus,
    JobEmbedding,
    Match,
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
)
from matching.serializers import (
    AdminMatchSerializer,
    CandidateMatchSerializer,
    EmployerMatchSerializer,
)


class VectorFoundationModelTests(TestCase):
    def setUp(self):
        self.candidate_user = User.objects.create_user(
            email="vector_candidate@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Vector Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Full Stack AI Engineer",
            current_title="Software Engineer",
            skills=["Python", "Django", "PostgreSQL", "pgvector"],
            role_categories=["Engineering"],
            experience_level=CandidateProfile.ExperienceLevel.SENIOR,
            profile_complete=True,
            open_to_matching=True,
        )

        self.employer_user = User.objects.create_user(
            email="vector_employer@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Vector Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Vector Tech Inc",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior AI Engineer",
            description="Developing AI models with pgvector and Django.",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            tech_stack=["Python", "PostgreSQL", "pgvector"],
            status=Job.Status.ACTIVE,
        )

    def test_candidate_resume_embedding_creation_and_defaults(self):
        resume_emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            content_hash="a" * 64,
            text_length=1500,
        )
        self.assertEqual(resume_emb.model_name, TARGET_EMBEDDING_MODEL)
        self.assertEqual(resume_emb.dimensions, TARGET_EMBEDDING_DIMENSIONS)
        self.assertEqual(resume_emb.status, EmbeddingStatus.PENDING)
        self.assertEqual(resume_emb.version, "v1")
        self.assertIsNone(resume_emb.embedding)
        self.assertEqual(self.candidate_profile.resume_embedding, resume_emb)

    def test_job_embedding_creation_and_defaults(self):
        job_emb = JobEmbedding.objects.create(
            job=self.job,
            content_hash="b" * 64,
            text_length=800,
        )
        self.assertEqual(job_emb.model_name, TARGET_EMBEDDING_MODEL)
        self.assertEqual(job_emb.dimensions, TARGET_EMBEDDING_DIMENSIONS)
        self.assertEqual(job_emb.status, EmbeddingStatus.PENDING)
        self.assertEqual(job_emb.version, "v1")
        self.assertIsNone(job_emb.embedding)
        self.assertEqual(self.job.job_embedding, job_emb)

    def test_one_to_one_uniqueness_candidate_resume_embedding(self):
        CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            content_hash="c" * 64,
        )
        # Attempting to create a second resume embedding for the same candidate profile must raise IntegrityError or ValidationError
        with self.assertRaises((IntegrityError, ValidationError)):
            CandidateResumeEmbedding.objects.create(
                candidate_profile=self.candidate_profile,
                content_hash="d" * 64,
            )

    def test_one_to_one_uniqueness_job_embedding(self):
        JobEmbedding.objects.create(
            job=self.job,
            content_hash="e" * 64,
        )
        # Attempting to create a second job embedding for the same job must raise IntegrityError or ValidationError
        with self.assertRaises((IntegrityError, ValidationError)):
            JobEmbedding.objects.create(
                job=self.job,
                content_hash="f" * 64,
            )

    def test_cascade_deletion_on_candidate_profile(self):
        CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            content_hash="g" * 64,
        )
        self.assertEqual(CandidateResumeEmbedding.objects.count(), 1)
        self.candidate_profile.delete()
        self.assertEqual(CandidateResumeEmbedding.objects.count(), 0)

    def test_cascade_deletion_on_job(self):
        JobEmbedding.objects.create(
            job=self.job,
            content_hash="h" * 64,
        )
        self.assertEqual(JobEmbedding.objects.count(), 1)
        self.job.delete()
        self.assertEqual(JobEmbedding.objects.count(), 0)

    def test_dimension_validation_enforces_2048(self):
        # Invalid dimension 1536 must fail validation
        invalid_emb = CandidateResumeEmbedding(
            candidate_profile=self.candidate_profile,
            dimensions=1536,
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_emb.full_clean()
        self.assertIn("Invalid embedding dimensions: expected 2048", str(ctx.exception))

    def test_model_name_validation_enforces_target_model(self):
        invalid_emb = JobEmbedding(
            job=self.job,
            model_name="text-embedding-3-small",
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_emb.full_clean()
        self.assertIn("Invalid model name", str(ctx.exception))

    def test_embedding_vector_length_validation(self):
        # Length mismatch (e.g. 3 dims instead of 2048) must fail
        short_vector = [0.1, 0.2, 0.3]
        invalid_emb = CandidateResumeEmbedding(
            candidate_profile=self.candidate_profile,
            embedding=short_vector,
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_emb.full_clean()
        self.assertIn("Embedding vector length mismatch", str(ctx.exception))

        # Exactly 2048 dims must succeed
        valid_vector = [0.001] * TARGET_EMBEDDING_DIMENSIONS
        valid_emb = CandidateResumeEmbedding(
            candidate_profile=self.candidate_profile,
            embedding=valid_vector,
        )
        valid_emb.full_clean()
        self.assertEqual(len(valid_emb.embedding), 2048)


class VectorSerializerPrivacyTests(TestCase):
    """
    Guarantees that private embedding records, raw vectors, and text hashes
    are NEVER exposed through any public, candidate, employer, or match serializers.
    """
    def setUp(self):
        self.candidate_user = User.objects.create_user(
            email="privacy_cand@example.com",
            password="TestPassword123!",
            role=User.Role.CANDIDATE,
            full_name="Privacy Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Security Architect",
            current_title="Lead Architect",
            skills=["Python", "Security", "PostgreSQL"],
            role_categories=["Engineering"],
            privacy_visibility=CandidateProfile.PrivacyVisibility.PUBLIC,
            profile_complete=True,
            open_to_matching=True,
        )
        self.resume_emb = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate_profile,
            status=EmbeddingStatus.COMPLETED,
            content_hash="secret_resume_hash_12345",
            text_length=2500,
            embedding=[0.01] * TARGET_EMBEDDING_DIMENSIONS,
        )

        self.employer_user = User.objects.create_user(
            email="privacy_emp@example.com",
            password="TestPassword123!",
            role=User.Role.EMPLOYER,
            full_name="Privacy Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Confidential Systems",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Principal Cryptographer",
            description="Confidential high-security job description.",
            tech_stack=["Cryptography", "Python"],
            status=Job.Status.ACTIVE,
        )
        self.job_emb = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            content_hash="secret_job_hash_67890",
            text_length=1200,
            embedding=[0.02] * TARGET_EMBEDDING_DIMENSIONS,
        )

        self.match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=92,
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )

    def test_candidate_profile_serializers_exclude_embedding_fields(self):
        # 1. CandidateProfileSerializer
        data = CandidateProfileSerializer(self.candidate_profile).data
        self.assertNotIn("resume_embedding", data)
        self.assertNotIn("embedding", data)
        self.assertNotIn("content_hash", data)
        self.assertNotIn("extracted_text", data)

        # 2. AdminCandidateListSerializer
        admin_data = AdminCandidateListSerializer(self.candidate_profile).data
        self.assertNotIn("resume_embedding", admin_data)
        self.assertNotIn("embedding", admin_data)
        self.assertNotIn("content_hash", admin_data)
        self.assertNotIn("extracted_text", admin_data)

        # 3. PublicTalentCardSerializer
        public_data = PublicTalentCardSerializer(self.candidate_profile).data
        self.assertNotIn("resume_embedding", public_data)
        self.assertNotIn("embedding", public_data)
        self.assertNotIn("content_hash", public_data)
        self.assertNotIn("extracted_text", public_data)

    def test_job_serializers_exclude_embedding_fields(self):
        # 1. JobSerializer
        job_data = JobSerializer(self.job).data
        self.assertNotIn("job_embedding", job_data)
        self.assertNotIn("embedding", job_data)
        self.assertNotIn("content_hash", job_data)

        # 2. JobPublicListSerializer
        pub_job_data = JobPublicListSerializer(self.job).data
        self.assertNotIn("job_embedding", pub_job_data)
        self.assertNotIn("embedding", pub_job_data)
        self.assertNotIn("content_hash", pub_job_data)

        # 3. EmployerJobPublicSerializer
        emp_job_data = EmployerJobPublicSerializer(self.job).data
        self.assertNotIn("job_embedding", emp_job_data)
        self.assertNotIn("embedding", emp_job_data)
        self.assertNotIn("content_hash", emp_job_data)

    def test_match_serializers_exclude_embedding_fields(self):
        # 1. CandidateMatchSerializer
        cand_match = CandidateMatchSerializer(self.match).data
        self.assertNotIn("embedding", cand_match)
        self.assertNotIn("resume_embedding", cand_match)
        self.assertNotIn("job_embedding", cand_match)
        self.assertNotIn("extracted_text", cand_match)

        # 2. EmployerMatchSerializer
        emp_match = EmployerMatchSerializer(self.match).data
        self.assertNotIn("embedding", emp_match)
        self.assertNotIn("resume_embedding", emp_match)
        self.assertNotIn("job_embedding", emp_match)
        self.assertNotIn("extracted_text", emp_match)

        # 3. AdminMatchSerializer
        admin_match = AdminMatchSerializer(self.match).data
        self.assertNotIn("embedding", admin_match)
        self.assertNotIn("resume_embedding", admin_match)
        self.assertNotIn("job_embedding", admin_match)
        self.assertNotIn("extracted_text", admin_match)
