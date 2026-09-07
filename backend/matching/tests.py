import uuid
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from handoffs.models import HandoffRequest
from jobs.models import Job
from .models import Match
from .services import (
    combined_match_score,
    compute_experience_score,
    compute_skill_overlap_score,
    parse_skills,
    resolve_match_status,
    run_matching_for_candidate,
    run_matching_for_job,
    skill_matches,
)


class MatchingAlgorithmUnitTests(TestCase):
    def test_parse_skills(self):
        parsed = parse_skills("Python, Django; PostgreSQL\nRedis|AWS")
        self.assertEqual(parsed, ["python", "django", "postgresql", "redis", "aws"])

    def test_skill_matches_substring(self):
        self.assertTrue(skill_matches("react.js", "react"))
        self.assertTrue(skill_matches("react", "react.js"))
        self.assertTrue(skill_matches("amazon web services (aws)", "aws"))
        self.assertFalse(skill_matches("python", "java"))

    def test_skill_overlap_score(self):
        candidate_skills = ["python", "django", "postgresql", "docker"]
        job_skills = ["python", "django", "kubernetes", "aws"]
        # 2 out of 4 = 50%
        score = compute_skill_overlap_score(candidate_skills, job_skills)
        self.assertEqual(score, 50)

        # Empty job skills = 40 (fallback)
        self.assertEqual(compute_skill_overlap_score(candidate_skills, []), 40)
        # Empty candidate skills = 0
        self.assertEqual(compute_skill_overlap_score([], job_skills), 0)

    def test_experience_score(self):
        # Candidate >= Job
        self.assertEqual(compute_experience_score("senior", "senior"), 100)
        self.assertEqual(compute_experience_score("lead", "senior"), 100)
        self.assertEqual(compute_experience_score("senior", "mid"), 100)

        # 1 level below (diff == -1)
        self.assertEqual(compute_experience_score("mid", "senior"), 70)
        self.assertEqual(compute_experience_score("junior", "mid"), 70)

        # 2+ levels below
        self.assertEqual(compute_experience_score("junior", "senior"), 40)
        self.assertEqual(compute_experience_score("junior", "lead"), 40)

        # Unknown / missing
        self.assertEqual(compute_experience_score(None, "senior"), 50)
        self.assertEqual(compute_experience_score("senior", None), 50)
        self.assertEqual(compute_experience_score("unknown", "senior"), 50)

    def test_combined_match_score(self):
        # 100% skill, 100% exp -> 100
        self.assertEqual(combined_match_score(100, 100), 100)
        # 50% skill, 70% exp -> 50*0.7 + 70*0.3 = 35 + 21 = 56
        self.assertEqual(combined_match_score(50, 70), 56)
        # 90% skill, 70% exp -> 90*0.7 + 70*0.3 = 63 + 21 = 84
        self.assertEqual(combined_match_score(90, 70), 84)

    def test_resolve_match_status_mutual_fit(self):
        # candidate interested + employer shortlisted -> mutual fit
        self.assertEqual(
            resolve_match_status(Match.Status.CANDIDATE_INTERESTED, Match.Status.EMPLOYER_SHORTLISTED),
            Match.Status.MUTUAL_FIT,
        )
        # employer shortlisted + candidate interested -> mutual fit
        self.assertEqual(
            resolve_match_status(Match.Status.EMPLOYER_SHORTLISTED, Match.Status.CANDIDATE_INTERESTED),
            Match.Status.MUTUAL_FIT,
        )
        # rejection overrides
        self.assertEqual(
            resolve_match_status(Match.Status.CANDIDATE_INTERESTED, Match.Status.REJECTED),
            Match.Status.REJECTED,
        )


class MatchApiAndRunnerTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.candidate_user = User.objects.create_user(
            email="candidate@test.com", password="Password123!", role=User.Role.CANDIDATE, full_name="Alice Candidate"
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Staff Python Engineer",
            skills=["python", "django", "postgresql", "redis", "celery", "aws"],
            experience_level="lead",
            profile_complete=True,
            open_to_matching=True,
        )

        self.employer_user = User.objects.create_user(
            email="employer@acme.com", password="Password123!", role=User.Role.EMPLOYER, full_name="Bob Employer"
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Acme Corp",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Principal Backend Engineer",
            description="Leading backend systems.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django", "postgresql", "celery"],
            salary_range="$160k - $200k",
            status=Job.Status.ACTIVE,
        )

        self.employer2_user = User.objects.create_user(
            email="employer2@beta.com", password="Password123!", role=User.Role.EMPLOYER, full_name="Charlie Beta"
        )
        self.admin = User.objects.create_superuser(
            email="admin@test.com", password="AdminPassword123!", full_name="Staff Admin"
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_run_matching_for_candidate(self):
        result = run_matching_for_candidate(str(self.candidate_profile.id))
        self.assertEqual(result["matched"], 1)

        match = Match.objects.get(candidate_profile=self.candidate_profile, job=self.job)
        self.assertEqual(match.match_score, 100)  # 100% skill overlap + 100% exp (lead >= senior)
        self.assertFalse(match.visible_to_employer)
        self.assertIsNotNone(match.recruiter_notified_at)

    def test_run_matching_for_job(self):
        result = run_matching_for_job(str(self.job.id))
        self.assertEqual(result["matched"], 1)

    def test_candidate_view_and_interest(self):
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )

        # Candidate views match list
        self._auth(self.candidate_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["job"]["title"], "Principal Backend Engineer")

        # Candidate marks interest
        res = self.client.patch(
            f"/api/v1/matches/{match.id}/",
            {"status": "candidate_interested"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "candidate_interested")
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.CANDIDATE_INTERESTED)

    def test_mutual_fit_creates_handoff(self):
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            status=Match.Status.CANDIDATE_INTERESTED,
            visible_to_employer=True,
        )

        # Employer shortlists candidate
        self._auth(self.employer_user)
        res = self.client.patch(
            f"/api/v1/matches/{match.id}/",
            {"status": "employer_shortlisted"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "mutual_fit")

        # Verify atomic handoff creation
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.MUTUAL_FIT)
        self.assertTrue(HandoffRequest.objects.filter(match=match).exists())

    def test_admin_action_gate(self):
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            status=Match.Status.SUGGESTED,
            visible_to_employer=False,
        )

        # Employer cannot see match yet
        self._auth(self.employer_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

        # Admin approves match
        self._auth(self.admin)
        res = self.client.patch(
            f"/api/v1/matches/{match.id}/admin-action/",
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        match.refresh_from_db()
        self.assertTrue(match.visible_to_employer)

        # Now employer sees the match
        self._auth(self.employer_user)
        res = self.client.get("/api/v1/matches/")
        self.assertEqual(len(res.data), 1)

    def test_employer_isolation(self):
        match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            status=Match.Status.SUGGESTED,
            visible_to_employer=True,
        )

        # Employer 2 tries to update Employer 1's match -> 403 Forbidden
        self._auth(self.employer2_user)
        res = self.client.patch(
            f"/api/v1/matches/{match.id}/",
            {"status": "employer_shortlisted"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
