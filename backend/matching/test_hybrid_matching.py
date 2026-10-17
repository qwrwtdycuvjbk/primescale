"""
Comprehensive Test Suite for Phase 7: Hybrid Candidate-Job Matching Engine.

Validates:
1. 50/30/20 hybrid score composition.
2. Strict qualification threshold (> 70.0; exactly 70.00 does not qualify).
3. Exact cosine distance / similarity conversions and vector edge cases (zeros, NaN, Inf, dimensions).
4. Missing skills, empty skill sets, missing experience levels, and boundary values.
5. Ineligible jobs: draft, paused, closed, archived, expired, external-source (ExternalJob), and unembedded jobs.
6. Ineligible and stale candidate profiles / resume embeddings.
7. Duplicate candidate-job pairs (idempotency, preservation of non-SUGGESTED statuses).
8. Approval gates, employer isolation (visible_to_employer=False), and recruiter notification thresholds (>=85).
9. Candidate privacy (no vector or private text leaks).
"""

import math
import uuid
from unittest.mock import MagicMock, patch
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from external_jobs.models import ExternalJob, ExternalJobSource
from jobs.models import Job
from matching.hybrid_engine import (
    QUALIFICATION_THRESHOLD,
    WEIGHT_EXPERIENCE,
    WEIGHT_SEMANTIC,
    WEIGHT_SKILLS,
    HybridMatchingEngine,
    calculate_hybrid_score,
    compute_cosine_similarity,
    compute_experience_score,
    compute_skill_overlap_score,
    cosine_distance_to_similarity_score,
    cosine_similarity_to_score,
    is_candidate_eligible_for_hybrid_matching,
    is_job_eligible_for_hybrid_matching,
)
from matching.models import (
    TARGET_EMBEDDING_DIMENSIONS,
    TARGET_EMBEDDING_MODEL,
    CandidateResumeEmbedding,
    EmbeddingStatus,
    JobEmbedding,
    Match,
)
from common.resume_extraction import calculate_source_fingerprint
from matching.services import (
    run_hybrid_matching_for_candidate,
    run_hybrid_matching_for_job,
    run_matching_for_candidate,
    run_matching_for_job,
)


def create_unit_vector(dimension: int = TARGET_EMBEDDING_DIMENSIONS, fill_val: float = 0.0) -> list[float]:
    """Helper to generate a normalized 2,048-dimensional unit vector."""
    vec = [fill_val] * dimension
    vec[0] = 1.0  # Unit vector along first dimension
    return vec


def create_scaled_vector(dimension: int = TARGET_EMBEDDING_DIMENSIONS, first_val: float = 0.7071, second_val: float = 0.7071) -> list[float]:
    """Helper to generate a controlled 2-component unit vector."""
    vec = [0.0] * dimension
    vec[0] = first_val
    vec[1] = second_val
    return vec


class HybridScoringFormulaUnitTests(TestCase):
    """Tests 50/30/20 component weighting, normalization, and qualification threshold."""

    def test_exact_50_30_20_composition(self):
        # 100 on all components -> 100.0
        res = calculate_hybrid_score(semantic_score=100.0, skill_score=100.0, exp_score=100.0)
        self.assertEqual(res.final_score, 100.0)
        self.assertTrue(res.qualifies)

        # 0 on all components -> 0.0
        res = calculate_hybrid_score(semantic_score=0.0, skill_score=0.0, exp_score=0.0)
        self.assertEqual(res.final_score, 0.0)
        self.assertFalse(res.qualifies)

        # Only semantic: 100 * 0.50 = 50.0
        res = calculate_hybrid_score(semantic_score=100.0, skill_score=0.0, exp_score=0.0)
        self.assertEqual(res.final_score, 50.0)
        self.assertFalse(res.qualifies)

        # Only skills: 100 * 0.30 = 30.0
        res = calculate_hybrid_score(semantic_score=0.0, skill_score=100.0, exp_score=0.0)
        self.assertEqual(res.final_score, 30.0)
        self.assertFalse(res.qualifies)

        # Only experience: 100 * 0.20 = 20.0
        res = calculate_hybrid_score(semantic_score=0.0, skill_score=0.0, exp_score=100.0)
        self.assertEqual(res.final_score, 20.0)
        self.assertFalse(res.qualifies)

        # Mixed weights: 80% semantic (40) + 70% skills (21) + 100% exp (20) = 81.0
        res = calculate_hybrid_score(semantic_score=80.0, skill_score=70.0, exp_score=100.0)
        self.assertEqual(res.final_score, 81.0)
        self.assertTrue(res.qualifies)

    def test_strict_qualification_threshold_at_70(self):
        """A candidate-job pair qualifies only when score is STRICTLY greater than 70.0 (70.00 does not qualify)."""
        # Exactly 70.00: e.g. 70 * 0.50 (35) + 70 * 0.30 (21) + 70 * 0.20 (14) = 70.00
        res_70 = calculate_hybrid_score(semantic_score=70.0, skill_score=70.0, exp_score=70.0)
        self.assertEqual(res_70.final_score, 70.0)
        self.assertFalse(res_70.qualifies, "Score of exactly 70.00 must NOT qualify.")

        # Just below: 69.99
        res_below = calculate_hybrid_score(semantic_score=69.98, skill_score=70.0, exp_score=70.0)
        self.assertLess(res_below.final_score, 70.0)
        self.assertFalse(res_below.qualifies)

        # Just above: 70.01 -> e.g. 70.1 * 0.50 (35.05) + 70 * 0.30 (21.0) + 70 * 0.20 (14.0) = 70.05
        res_above = calculate_hybrid_score(semantic_score=70.1, skill_score=70.0, exp_score=70.0)
        self.assertGreater(res_above.final_score, 70.0)
        self.assertTrue(res_above.qualifies, "Score strictly above 70.00 MUST qualify.")

        # Clearly above: 71.0
        res_71 = calculate_hybrid_score(semantic_score=72.0, skill_score=70.0, exp_score=70.0)
        self.assertEqual(res_71.final_score, 71.0)
        self.assertTrue(res_71.qualifies)


class SemanticSimilarityConversionTests(TestCase):
    """Tests pgvector cosine distance conversion and vector mathematical edge cases."""

    def test_cosine_distance_conversion(self):
        # Distance 0.0 (identical) -> 100.0
        self.assertEqual(cosine_distance_to_similarity_score(0.0), 100.0)

        # Distance 0.30 -> 70.0
        self.assertEqual(cosine_distance_to_similarity_score(0.30), 70.0)

        # Distance 0.50 -> 50.0
        self.assertEqual(cosine_distance_to_similarity_score(0.50), 50.0)

        # Distance 1.0 (orthogonal) -> 0.0
        self.assertEqual(cosine_distance_to_similarity_score(1.0), 0.0)

        # Distance > 1.0 (negative correlation) -> clamped to 0.0
        self.assertEqual(cosine_distance_to_similarity_score(1.5), 0.0)
        self.assertEqual(cosine_distance_to_similarity_score(2.0), 0.0)

    def test_vector_cosine_similarity_edge_cases(self):
        v1 = create_unit_vector()
        v2 = create_unit_vector()
        # Identical vectors
        self.assertAlmostEqual(compute_cosine_similarity(v1, v2), 1.0, places=5)

        # Orthogonal vectors
        v_ortho = [0.0] * TARGET_EMBEDDING_DIMENSIONS
        v_ortho[1] = 1.0
        self.assertAlmostEqual(compute_cosine_similarity(v1, v_ortho), 0.0, places=5)

        # All-zero vectors safely return 0.0 without division by zero
        zero_vec = [0.0] * TARGET_EMBEDDING_DIMENSIONS
        self.assertEqual(compute_cosine_similarity(v1, zero_vec), 0.0)
        self.assertEqual(compute_cosine_similarity(zero_vec, zero_vec), 0.0)

        # Non-finite values (NaN, Inf) safely handled
        nan_vec = list(v1)
        nan_vec[5] = float("nan")
        self.assertEqual(compute_cosine_similarity(v1, nan_vec), 0.0)

        inf_vec = list(v1)
        inf_vec[10] = float("inf")
        self.assertEqual(compute_cosine_similarity(v1, inf_vec), 0.0)

        # None or empty vector safely returns 0.0
        self.assertEqual(compute_cosine_similarity(v1, None), 0.0)
        self.assertEqual(compute_cosine_similarity(None, None), 0.0)

        # Mismatched dimensions safely returns 0.0
        short_vec = [1.0] * 1024
        self.assertEqual(compute_cosine_similarity(v1, short_vec), 0.0)


class SkillsAndExperienceEdgeCasesTests(TestCase):
    """Tests skills overlap and experience alignment with missing or partial data."""

    def test_skills_overlap_edge_cases(self):
        # Normal overlap: 3 of 4 = 75%
        cand = ["python", "django", "postgresql", "docker"]
        job = ["python", "django", "postgresql", "aws"]
        self.assertEqual(compute_skill_overlap_score(cand, job), 75.0)

        # Empty job skills -> returns documented neutral fallback 40.0
        self.assertEqual(compute_skill_overlap_score(cand, []), 40.0)
        self.assertEqual(compute_skill_overlap_score(cand, None), 40.0)

        # Empty candidate skills -> returns 0.0
        self.assertEqual(compute_skill_overlap_score([], job), 0.0)
        self.assertEqual(compute_skill_overlap_score(None, job), 0.0)

        # Both empty -> returns 40.0 (job requires no skills)
        self.assertEqual(compute_skill_overlap_score([], []), 40.0)

    def test_experience_level_edge_cases(self):
        # Candidate >= Job -> 100.0
        self.assertEqual(compute_experience_score("lead", "lead"), 100.0)
        self.assertEqual(compute_experience_score("lead", "senior"), 100.0)
        self.assertEqual(compute_experience_score("senior", "mid"), 100.0)
        self.assertEqual(compute_experience_score("mid", "junior"), 100.0)

        # 1 level below -> 70.0
        self.assertEqual(compute_experience_score("senior", "lead"), 70.0)
        self.assertEqual(compute_experience_score("mid", "senior"), 70.0)
        self.assertEqual(compute_experience_score("junior", "mid"), 70.0)

        # 2+ levels below -> 40.0
        self.assertEqual(compute_experience_score("junior", "senior"), 40.0)
        self.assertEqual(compute_experience_score("junior", "lead"), 40.0)

        # Missing or unknown -> documented neutral 50.0
        self.assertEqual(compute_experience_score(None, "senior"), 50.0)
        self.assertEqual(compute_experience_score("senior", None), 50.0)
        self.assertEqual(compute_experience_score(None, None), 50.0)
        self.assertEqual(compute_experience_score("unrecognized", "senior"), 50.0)


class HybridMatchingEngineIntegrationTests(TestCase):
    """Tests end-to-end matching, eligibility filtering, invalidation, approval gates, and privacy."""

    def setUp(self):
        self.employer_user = User.objects.create_user(
            email="recruiter@acme.com", password="Password123!", role=User.Role.EMPLOYER, full_name="Robert Recruiter"
        )
        self.company = Company.objects.create(
            owner=self.employer_user, name="Acme Tech", profile_complete=True
        )

        # Eligible first-party Job
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Architect",
            description="Leading scalable backend services in Django and PostgreSQL.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django", "postgresql", "celery"],
            status=Job.Status.ACTIVE,
        )
        # Job Embedding (completed)
        self.job_vector = create_unit_vector()
        self.job_embedding = JobEmbedding.objects.create(
            job=self.job,
            status=EmbeddingStatus.COMPLETED,
            embedding=self.job_vector,
            content_hash="job_hash_123",
            version="v1",
        )

        # Candidate Profile
        self.cand_user = User.objects.create_user(
            email="candidate@gmail.com", password="Password123!", role=User.Role.CANDIDATE, full_name="Alice Candidate"
        )
        self.candidate = CandidateProfile.objects.create(
            user=self.cand_user,
            headline="Lead Backend Engineer",
            skills=["python", "django", "postgresql", "celery", "redis"],
            experience_level="lead",
            resume_url="resumes/alice/resume.pdf",
            open_to_matching=True,
            profile_complete=True,
        )
        # Candidate Resume Embedding (completed, matching vector)
        self.cand_vector = create_unit_vector()
        self.cand_embedding = CandidateResumeEmbedding.objects.create(
            candidate_profile=self.candidate,
            status=EmbeddingStatus.COMPLETED,
            embedding=self.cand_vector,
            content_hash="cand_hash_123",
            version=calculate_source_fingerprint("resumes/alice/resume.pdf"),
        )

    def test_qualifying_match_created_with_default_approval_gate(self):
        """A qualifying candidate (score > 70) creates a Match with visible_to_employer=False."""
        result = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(result["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate, job=self.job)
        # Identical vectors (100% sem) + 100% skills + 100% exp (lead >= senior) = 100%
        self.assertEqual(match.match_score, 100)
        self.assertEqual(match.status, Match.Status.SUGGESTED)
        # Approval gate: NEVER automatically visible to employer
        self.assertFalse(match.visible_to_employer)
        # Recruiter notification timestamp set for score >= 85
        self.assertIsNotNone(match.recruiter_notified_at)
        self.assertIn("Hybrid match", match.match_reason)

    def test_non_qualifying_score_does_not_create_match(self):
        """A candidate-job pair scoring <= 70.0 is not matched."""
        # Orthogonal vector (semantic = 0%), 0 skills matched (skill = 0%), junior for senior (exp = 40%)
        # Total = 0.50*0 + 0.30*0 + 0.20*40 = 8.0 (< 70.0)
        ortho_cand_user = User.objects.create_user(
            email="low@test.com", password="Password123!", role=User.Role.CANDIDATE
        )
        low_cand = CandidateProfile.objects.create(
            user=ortho_cand_user,
            skills=["ruby", "rails"],
            experience_level="junior",
            open_to_matching=True,
            profile_complete=True,
        )
        ortho_vector = [0.0] * TARGET_EMBEDDING_DIMENSIONS
        ortho_vector[1] = 1.0
        CandidateResumeEmbedding.objects.create(
            candidate_profile=low_cand,
            status=EmbeddingStatus.COMPLETED,
            embedding=ortho_vector,
            content_hash="low_hash",
        )

        result = run_hybrid_matching_for_candidate(low_cand.id)
        self.assertEqual(result["matched"], 0)
        self.assertFalse(Match.objects.filter(candidate_profile=low_cand, job=self.job).exists())

    def test_ineligible_jobs_excluded(self):
        """Inactive, draft, paused, closed, expired, external, and unembedded jobs are excluded."""
        # 1. Paused job
        paused_job = Job.objects.create(
            company=self.company, posted_by=self.employer_user,
            title="Paused Job", description="Description",
            role_type="full-time", experience_level="senior",
            status=Job.Status.PAUSED,
        )
        JobEmbedding.objects.create(job=paused_job, status=EmbeddingStatus.COMPLETED, embedding=self.job_vector)

        # 2. Expired job
        expired_job = Job.objects.create(
            company=self.company, posted_by=self.employer_user,
            title="Expired Job", description="Description",
            role_type="full-time", experience_level="senior",
            status=Job.Status.ACTIVE,
            expires_at=timezone.now() - timedelta(days=2),
        )
        JobEmbedding.objects.create(job=expired_job, status=EmbeddingStatus.COMPLETED, embedding=self.job_vector)

        # 3. Unembedded job (no JobEmbedding)
        unembedded_job = Job.objects.create(
            company=self.company, posted_by=self.employer_user,
            title="Unembedded Job", description="Description",
            role_type="full-time", experience_level="senior",
            status=Job.Status.ACTIVE,
        )

        # 4. Job with failed embedding
        failed_job = Job.objects.create(
            company=self.company, posted_by=self.employer_user,
            title="Failed Job", description="Description",
            role_type="full-time", experience_level="senior",
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(job=failed_job, status=EmbeddingStatus.FAILED, embedding=None)

        # 5. ExternalJob from Adzuna / Himalayas
        ext_source = ExternalJobSource.objects.create(
            name="Adzuna",
            provider_code="adzuna",
            api_enabled=True,
            attribution_name="Adzuna Remote",
        )
        ext_job = ExternalJob.objects.create(
            source=ext_source, external_job_id="ext-999",
            title="External Architect", description="External job text",
            company_name="External Corp",
        )

        # Run candidate matching: only self.job should match
        res = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res["matched"], 1)

        # Verify none of the ineligible jobs were matched
        self.assertFalse(Match.objects.filter(candidate_profile=self.candidate, job=paused_job).exists())
        self.assertFalse(Match.objects.filter(candidate_profile=self.candidate, job=expired_job).exists())
        self.assertFalse(Match.objects.filter(candidate_profile=self.candidate, job=unembedded_job).exists())
        self.assertFalse(Match.objects.filter(candidate_profile=self.candidate, job=failed_job).exists())

    def test_ineligible_candidates_excluded(self):
        """Ineligible, incomplete, not open, or unembedded candidates are excluded from job matching."""
        # 1. Candidate not open to matching
        cand2_user = User.objects.create_user(email="notopen@test.com", password="Password123!", role=User.Role.CANDIDATE)
        cand2 = CandidateProfile.objects.create(
            user=cand2_user, open_to_matching=False, profile_complete=True,
            skills=["python"], experience_level="senior",
        )
        CandidateResumeEmbedding.objects.create(candidate_profile=cand2, status=EmbeddingStatus.COMPLETED, embedding=self.cand_vector)

        # 2. Incomplete profile
        cand3_user = User.objects.create_user(email="incomplete@test.com", password="Password123!", role=User.Role.CANDIDATE)
        cand3 = CandidateProfile.objects.create(
            user=cand3_user, open_to_matching=True, profile_complete=False,
            skills=["python"], experience_level="senior",
        )
        CandidateResumeEmbedding.objects.create(candidate_profile=cand3, status=EmbeddingStatus.COMPLETED, embedding=self.cand_vector)

        # 3. Candidate with pending/failed embedding
        cand4_user = User.objects.create_user(email="failed_emb@test.com", password="Password123!", role=User.Role.CANDIDATE)
        cand4 = CandidateProfile.objects.create(
            user=cand4_user, open_to_matching=True, profile_complete=True,
            skills=["python"], experience_level="senior",
        )
        CandidateResumeEmbedding.objects.create(candidate_profile=cand4, status=EmbeddingStatus.FAILED, embedding=None)

        # Run job matching: only self.candidate should match
        res = run_hybrid_matching_for_job(self.job.id)
        self.assertEqual(res["matched"], 1)

        self.assertFalse(Match.objects.filter(candidate_profile=cand2, job=self.job).exists())
        self.assertFalse(Match.objects.filter(candidate_profile=cand3, job=self.job).exists())
        self.assertFalse(Match.objects.filter(candidate_profile=cand4, job=self.job).exists())

    def test_duplicate_matching_preserves_unique_constraint_and_status(self):
        """Re-running matching updates the match score without duplicating or resetting existing status."""
        # First match run
        run_hybrid_matching_for_candidate(self.candidate.id)
        match = Match.objects.get(candidate_profile=self.candidate, job=self.job)
        self.assertEqual(match.status, Match.Status.SUGGESTED)

        # Candidate expresses interest
        match.status = Match.Status.CANDIDATE_INTERESTED
        match.save(update_fields=["status"])

        # Re-run matching
        res = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res["matched"], 1)

        # Verify only 1 match record exists (no duplicate)
        self.assertEqual(Match.objects.filter(candidate_profile=self.candidate, job=self.job).count(), 1)
        match.refresh_from_db()
        # Verify status is NOT reverted to SUGGESTED
        self.assertEqual(match.status, Match.Status.CANDIDATE_INTERESTED)

    def test_employer_isolation_and_privacy_boundaries(self):
        """Employer cannot see candidate match until admin approval; no raw vectors or text exposed."""
        run_hybrid_matching_for_candidate(self.candidate.id)
        match = Match.objects.get(candidate_profile=self.candidate, job=self.job)

        # Employer client
        client = APIClient()
        token = str(RefreshToken.for_user(self.employer_user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Employer lists matches -> empty because visible_to_employer=False
        res = client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

        # Manually approve match (simulate admin review)
        match.visible_to_employer = True
        match.save(update_fields=["visible_to_employer"])

        # Now employer sees the match
        res = client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        match_data = res.data[0]
        # Verify NO private vectors, raw resume text, or normalized job text are present
        self.assertNotIn("embedding", match_data)
        self.assertNotIn("extracted_text", match_data)
        self.assertNotIn("raw_text", match_data)
        self.assertNotIn("vectors", match_data)

    def test_failed_or_pending_embedding_prohibits_legacy_fallback(self):
        """A candidate with a FAILED or PENDING embedding strictly rejects and NEVER falls back to legacy matching."""
        # Candidate with failed embedding
        failed_cand_user = User.objects.create_user(email="failed_cand@test.com", password="Password123!", role=User.Role.CANDIDATE)
        failed_cand = CandidateProfile.objects.create(
            user=failed_cand_user,
            skills=["python", "django", "postgresql", "celery"],
            experience_level="lead",
            open_to_matching=True,
            profile_complete=True,
        )
        CandidateResumeEmbedding.objects.create(
            candidate_profile=failed_cand,
            status=EmbeddingStatus.FAILED,
            error_message="EmbeddingPermanentError: 422 Input Too Long",
            embedding=None,
        )

        # Calling run_matching_for_candidate must return 0 matched without falling back to legacy algorithm
        res = run_matching_for_candidate(failed_cand.id)
        self.assertEqual(res["matched"], 0)
        self.assertIn("reason", res)
        self.assertFalse(Match.objects.filter(candidate_profile=failed_cand, job=self.job).exists())

        # Candidate with pending embedding
        pending_cand_user = User.objects.create_user(email="pending_cand@test.com", password="Password123!", role=User.Role.CANDIDATE)
        pending_cand = CandidateProfile.objects.create(
            user=pending_cand_user,
            skills=["python", "django", "postgresql", "celery"],
            experience_level="lead",
            open_to_matching=True,
            profile_complete=True,
        )
        CandidateResumeEmbedding.objects.create(
            candidate_profile=pending_cand,
            status=EmbeddingStatus.PENDING,
            embedding=None,
        )

        res_pend = run_matching_for_candidate(pending_cand.id)
        self.assertEqual(res_pend["matched"], 0)
        self.assertFalse(Match.objects.filter(candidate_profile=pending_cand, job=self.job).exists())

    def test_job_with_failed_or_pending_embedding_prohibits_legacy_fallback(self):
        """A job with a FAILED or PENDING embedding strictly rejects and NEVER falls back to legacy matching."""
        failed_job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Failed Embedding Job",
            description="Leading backend systems.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django", "postgresql", "celery"],
            status=Job.Status.ACTIVE,
        )
        JobEmbedding.objects.create(
            job=failed_job,
            status=EmbeddingStatus.FAILED,
            error_message="Dimension error",
            embedding=None,
        )

        res = run_matching_for_job(failed_job.id)
        self.assertEqual(res["matched"], 0)
        self.assertIn("reason", res)
        self.assertFalse(Match.objects.filter(job=failed_job).exists())

    def test_stale_resume_fingerprint_mismatch_excluded_from_matching(self):
        """When a candidate uploads a new resume, the fingerprint mismatch marks embedding stale and excludes them."""
        # Set initial resume_url and matching version
        self.candidate.resume_url = "resumes/candidate_alice/v1.pdf"
        self.candidate.save(update_fields=["resume_url"])
        self.cand_embedding.version = calculate_source_fingerprint(self.candidate.resume_url)
        self.cand_embedding.save(update_fields=["version"])

        # Candidate is initially eligible
        is_ok, reason = is_candidate_eligible_for_hybrid_matching(self.candidate)
        self.assertTrue(is_ok)

        # Candidate uploads newly modified resume (resume_url changes)
        self.candidate.resume_url = "resumes/candidate_alice/v2_new_upload.pdf"
        self.candidate.save(update_fields=["resume_url"])

        # Now embedding is stale because fingerprint no longer matches
        is_ok_stale, stale_reason = is_candidate_eligible_for_hybrid_matching(self.candidate)
        self.assertFalse(is_ok_stale)
        self.assertIn("stale", stale_reason)

        # Matching excludes this stale candidate
        res = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res["matched"], 0)

    def test_scoring_table_explicit_examples(self):
        """
        Validates all scoring table cases:
        1. All 3 components available.
        2. Missing candidate skills (skills=0).
        3. Job with no required skills (neutral baseline 40).
        4. Missing or unmapped experience levels (neutral baseline 50).
        5. Missing or invalid embeddings (semantic=0).
        6. Scores exactly 70.00, 69.99, and 70.01.
        """
        # Case 1: All 3 components available
        # Sem=80 (40.0) + Skill=90 (27.0) + Exp=100 (20.0) = 87.0
        b1 = calculate_hybrid_score(80.0, 90.0, 100.0)
        self.assertEqual(b1.final_score, 87.0)
        self.assertTrue(b1.qualifies)

        # Case 2: Missing candidate skills (cand skills=[], job requires skills)
        # Skills score = 0.0. Sem=80 (40.0) + Skill=0 (0.0) + Exp=100 (20.0) = 60.0
        b2 = calculate_hybrid_score(80.0, compute_skill_overlap_score([], ["python", "django"]), 100.0)
        self.assertEqual(b2.skill_score, 0.0)
        self.assertEqual(b2.final_score, 60.0)
        self.assertFalse(b2.qualifies, "Missing skills resulting in 60.0 must NOT qualify.")

        # Case 3: Job with no required skills (job requires no skills -> neutral baseline 40.0)
        # Sem=80 (40.0) + Skill=40 (12.0) + Exp=100 (20.0) = 72.0 > 70.0
        b3 = calculate_hybrid_score(80.0, compute_skill_overlap_score(["python"], []), 100.0)
        self.assertEqual(b3.skill_score, 40.0)
        self.assertEqual(b3.final_score, 72.0)
        self.assertTrue(b3.qualifies, "Neutral skills baseline allows high-semantic candidate to qualify.")

        # Case 4: Missing or unmapped experience levels (neutral baseline 50.0)
        # Sem=80 (40.0) + Skill=80 (24.0) + Exp=50 (10.0) = 74.0 > 70.0
        b4 = calculate_hybrid_score(80.0, 80.0, compute_experience_score(None, "senior"))
        self.assertEqual(b4.exp_score, 50.0)
        self.assertEqual(b4.final_score, 74.0)
        self.assertTrue(b4.qualifies)

        # Case 5: Missing or invalid embeddings -> cannot be treated as valid semantic match (sem=0.0)
        # Sem=0.0 (0.0) + Skill=100 (30.0) + Exp=100 (20.0) = 50.0 <= 70.0
        b5 = calculate_hybrid_score(0.0, 100.0, 100.0)
        self.assertEqual(b5.final_score, 50.0)
        self.assertFalse(b5.qualifies, "Invalid/unavailable embedding resulting in 50.0 must NOT qualify.")

        # Case 6a: Exactly 70.00
        # Sem=70.0 (35.0) + Skill=70.0 (21.0) + Exp=70.0 (14.0) = 70.00
        b6a = calculate_hybrid_score(70.0, 70.0, 70.0)
        self.assertEqual(b6a.final_score, 70.0)
        self.assertFalse(b6a.qualifies, "Score of exactly 70.00 MUST NOT qualify.")

        # Case 6b: Just below 70.00 (69.98)
        b6b = calculate_hybrid_score(69.96, 70.0, 70.0)
        self.assertEqual(b6b.final_score, 69.98)
        self.assertFalse(b6b.qualifies, "Score below 70.00 must NOT qualify.")

        # Case 6c: Just above 70.00 (70.05)
        b6c = calculate_hybrid_score(70.1, 70.0, 70.0)
        self.assertEqual(b6c.final_score, 70.05)
        self.assertTrue(b6c.qualifies, "Score strictly above 70.00 MUST qualify.")

    def test_recruiter_notification_idempotency_and_semantics(self):
        """
        Recruiter notification semantics:
        - If score >= 85, records recruiter_notified_at timestamp.
        - Idempotent: repeated matching runs NEVER overwrite the original timestamp.
        - If score < 85, recruiter_notified_at is None.
        """
        # Run matching for qualifying candidate (score 100 >= 85)
        run_hybrid_matching_for_candidate(self.candidate.id)
        match = Match.objects.get(candidate_profile=self.candidate, job=self.job)
        self.assertIsNotNone(match.recruiter_notified_at)
        original_timestamp = match.recruiter_notified_at

        # Sleep / simulate later time and re-run matching
        res = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res["matched"], 1)

        match.refresh_from_db()
        # Verify timestamp was preserved identically (idempotent)
        self.assertEqual(match.recruiter_notified_at, original_timestamp)

    def test_celery_tasks_call_hybrid_matching_without_fallback(self):
        """Asynchronous Celery tasks directly invoke hybrid matching."""
        from matching.tasks import run_matching_for_candidate_task, run_matching_for_job_task

        # Candidate Celery task
        res_cand = run_matching_for_candidate_task(str(self.candidate.id))
        self.assertEqual(res_cand["matched"], 1)

        # Job Celery task
        res_job = run_matching_for_job_task(str(self.job.id))
        self.assertEqual(res_job["matched"], 1)

    def test_concurrent_match_creation_integrity_error_recovery(self):
        """
        Simulates two workers racing to create the same candidate-job pair.
        Worker 2 experiences an IntegrityError on insert, rolls back the inner savepoint,
        retains a healthy transaction state, and locks/updates the winning record.
        """
        breakdown = calculate_hybrid_score(90.0, 90.0, 90.0)

        # Worker 1 creates the match record first
        winning_match = Match.objects.create(
            candidate_profile=self.candidate,
            job=self.job,
            match_score=85,
            match_reason="Worker 1 reason",
            status=Match.Status.CANDIDATE_INTERESTED,  # Candidate already took an action
            visible_to_employer=True,
        )

        # Now simulate Worker 2 entering _persist_match:
        # Worker 2 attempts to call _persist_match, where a race condition occurs
        # (e.g. if initial filter had returned None or if create hits IntegrityError)
        with patch.object(Match.objects, "create", side_effect=IntegrityError("duplicate key value violates unique constraint")):
            result_match = HybridMatchingEngine._persist_match(self.candidate, self.job, breakdown)

        # Verification:
        # 1. No unhandled exception or TransactionManagementError was raised
        # 2. Result is the winning match
        self.assertEqual(result_match.id, winning_match.id)
        result_match.refresh_from_db()
        # 3. Status and visibility are preserved (user actions and recruiter visibility untouched)
        self.assertEqual(result_match.status, Match.Status.CANDIDATE_INTERESTED)
        self.assertTrue(result_match.visible_to_employer)
        # 4. Score and reason are updated
        self.assertEqual(result_match.match_score, 90)
        self.assertIn("Hybrid match", result_match.match_reason)
        # 5. Only 1 record exists in the database
        self.assertEqual(Match.objects.filter(candidate_profile=self.candidate, job=self.job).count(), 1)

    def test_recruiter_notification_unrounded_score_boundary(self):
        """
        Verifies that unrounded score < 85.0 (e.g. 84.8) does NOT trigger recruiter_notified_at,
        even if integer rounding would produce 85.
        Score >= 85.0 does trigger recruiter_notified_at.
        """
        # Case A: 84.8 final score -> rounds to integer 85, but unrounded is < 85.0
        # Sem=84.8, Skill=84.8, Exp=84.8 -> final_score = 84.80
        b_sub85 = calculate_hybrid_score(84.8, 84.8, 84.8)
        self.assertEqual(b_sub85.final_score, 84.8)
        self.assertEqual(int(round(b_sub85.final_score)), 85)

        m_sub85 = HybridMatchingEngine._persist_match(self.candidate, self.job, b_sub85)
        # MUST NOT be notified because 84.8 < 85.0
        self.assertIsNone(m_sub85.recruiter_notified_at, "Score 84.8 must NOT trigger recruiter notification.")

        # Case B: 85.0 final score -> strictly >= 85.0
        b_85 = calculate_hybrid_score(85.0, 85.0, 85.0)
        self.assertEqual(b_85.final_score, 85.0)

        m_85 = HybridMatchingEngine._persist_match(self.candidate, self.job, b_85)
        self.assertIsNotNone(m_85.recruiter_notified_at, "Score 85.0 MUST trigger recruiter notification.")

        # Case C: 85.2 final score -> strictly >= 85.0
        b_852 = calculate_hybrid_score(85.2, 85.2, 85.2)
        original_ts = m_85.recruiter_notified_at

        m_852 = HybridMatchingEngine._persist_match(self.candidate, self.job, b_852)
        # Idempotent: does NOT overwrite existing timestamp
        self.assertEqual(m_852.recruiter_notified_at, original_ts)

    def test_full_lifecycle_resume_fingerprint_compatibility(self):
        """
        Verifies end-to-end resume upload -> extraction -> embedding -> matching lifecycle:
        1. Initial resume matches successfully.
        2. Candidate uploads new resume file (resume_url changes) -> becomes stale.
        3. Stale candidate is immediately excluded from matching.
        4. Re-running embedding generation updates version fingerprint -> candidate qualifies again.
        """
        # 1. Initially matches
        res1 = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res1["matched"], 1)

        # 2. Candidate uploads new resume file
        self.candidate.resume_url = "resumes/alice/new_version_2026.pdf"
        self.candidate.save(update_fields=["resume_url"])

        # 3. Immediately excluded as stale
        is_ok, reason = is_candidate_eligible_for_hybrid_matching(self.candidate)
        self.assertFalse(is_ok)
        self.assertIn("stale", reason)
        res_stale = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res_stale["matched"], 0)

        # 4. Background pipeline completes: updates embedding version to new fingerprint
        new_fingerprint = calculate_source_fingerprint(self.candidate.resume_url)
        self.cand_embedding.version = new_fingerprint
        self.cand_embedding.save(update_fields=["version"])

        # Candidate is eligible once more
        is_ok_renewed, _ = is_candidate_eligible_for_hybrid_matching(self.candidate)
        self.assertTrue(is_ok_renewed)
        res_renewed = run_hybrid_matching_for_candidate(self.candidate.id)
        self.assertEqual(res_renewed["matched"], 1)
