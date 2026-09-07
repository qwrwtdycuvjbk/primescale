from django.test import TestCase
from django.db import IntegrityError
from accounts.models import User
from companies.models import Company, CompanyMember
from candidates.models import CandidateProfile
from jobs.models import Job
from matching.models import Match
from handoffs.models import HandoffRequest


class BackendFoundationTests(TestCase):
    def test_health_check_endpoint(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_user_email_uniqueness(self):
        User.objects.create_user(email="test@example.com", password="password123")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="test@example.com", password="password456")

    def test_candidate_profile_one_to_one(self):
        user = User.objects.create_user(email="candidate@example.com", role=User.Role.CANDIDATE)
        profile = CandidateProfile.objects.create(user=user, headline="Backend Dev")
        self.assertEqual(user.candidate_profile, profile)

        with self.assertRaises(IntegrityError):
            CandidateProfile.objects.create(user=user, headline="Duplicate")

    def test_company_owner_relationship(self):
        owner = User.objects.create_user(email="employer@example.com", role=User.Role.EMPLOYER)
        company = Company.objects.create(owner=owner, name="Acme Inc")
        self.assertEqual(owner.owned_company, company)

        with self.assertRaises(IntegrityError):
            Company.objects.create(owner=owner, name="Duplicate Inc")

    def test_company_member_uniqueness(self):
        owner = User.objects.create_user(email="owner@example.com", role=User.Role.EMPLOYER)
        company = Company.objects.create(owner=owner, name="TechCorp")
        member_user = User.objects.create_user(email="member@example.com", role=User.Role.EMPLOYER)

        CompanyMember.objects.create(company=company, user=member_user, member_role="recruiter")
        with self.assertRaises(IntegrityError):
            CompanyMember.objects.create(company=company, user=member_user, member_role="hiring_manager")

    def test_match_uniqueness(self):
        employer = User.objects.create_user(email="emp@example.com", role=User.Role.EMPLOYER)
        company = Company.objects.create(owner=employer, name="Cloud Inc")
        job = Job.objects.create(
            company=company,
            posted_by=employer,
            title="Senior Python Engineer",
            description="Django role",
            role_type="full-time",
            experience_level="senior",
        )

        candidate_user = User.objects.create_user(email="cand@example.com", role=User.Role.CANDIDATE)
        candidate_profile = CandidateProfile.objects.create(user=candidate_user)

        Match.objects.create(candidate_profile=candidate_profile, job=job, match_score=90)
        with self.assertRaises(IntegrityError):
            Match.objects.create(candidate_profile=candidate_profile, job=job, match_score=95)

    def test_handoff_request_uniqueness(self):
        employer = User.objects.create_user(email="emp2@example.com", role=User.Role.EMPLOYER)
        company = Company.objects.create(owner=employer, name="Devs Inc")
        job = Job.objects.create(
            company=company,
            posted_by=employer,
            title="DevOps Lead",
            description="Kubernetes role",
            role_type="full-time",
            experience_level="lead",
        )

        candidate_user = User.objects.create_user(email="cand2@example.com", role=User.Role.CANDIDATE)
        candidate_profile = CandidateProfile.objects.create(user=candidate_user)
        match = Match.objects.create(candidate_profile=candidate_profile, job=job, match_score=95)

        HandoffRequest.objects.create(match=match, status="pending")
        with self.assertRaises(IntegrityError):
            HandoffRequest.objects.create(match=match, status="contacted")
