import uuid
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.models import Match
from .models import HandoffRequest
from .services import create_mutual_fit_handoff, update_handoff_status


class HandoffApiAndServiceTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.candidate_user = User.objects.create_user(
            email="candidate@test.com", password="Password123!", role=User.Role.CANDIDATE, full_name="Candidate A"
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Engineer",
            skills=["python"],
            profile_complete=True,
            open_to_matching=True,
        )

        self.employer_user = User.objects.create_user(
            email="employer@test.com", password="Password123!", role=User.Role.EMPLOYER, full_name="Employer B"
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Alpha Corp",
            profile_complete=True,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Python Dev",
            description="Django backend.",
            role_type="full-time",
            experience_level="mid",
            tech_stack=["python", "django", "postgres"],
            salary_range="$100k - $120k",
            status=Job.Status.ACTIVE,
        )

        self.match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=90,
            status=Match.Status.MUTUAL_FIT,
            visible_to_employer=True,
        )

        self.admin = User.objects.create_superuser(
            email="admin@peopleremotely.com", password="AdminPassword123!", full_name="Admin Staff"
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_idempotent_handoff_creation(self):
        # Create first time
        handoff1 = create_mutual_fit_handoff(str(self.match.id))
        self.assertIsNotNone(handoff1)
        self.assertEqual(HandoffRequest.objects.filter(match=self.match).count(), 1)

        # Create second time -> returns same object, no duplicate
        handoff2 = create_mutual_fit_handoff(str(self.match.id))
        self.assertEqual(handoff1.id, handoff2.id)
        self.assertEqual(HandoffRequest.objects.filter(match=self.match).count(), 1)

    def test_admin_handoff_queue_and_updates(self):
        handoff = create_mutual_fit_handoff(str(self.match.id))

        # Admin lists handoff queue
        self._auth(self.admin)
        res = self.client.get("/api/v1/handoffs/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["status"], "pending")

        # Admin updates status to contacted + adds notes
        res = self.client.patch(
            f"/api/v1/handoffs/{handoff.id}/",
            {"status": "contacted", "notes": "Reached out to Alice and Bob on Slack."},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["handoff"]["status"], "contacted")
        self.assertEqual(res.data["handoff"]["notes"], "Reached out to Alice and Bob on Slack.")

        handoff.refresh_from_db()
        self.assertEqual(handoff.status, "contacted")
        self.assertEqual(handoff.notes, "Reached out to Alice and Bob on Slack.")

    def test_candidate_and_employer_forbidden(self):
        handoff = create_mutual_fit_handoff(str(self.match.id))

        # Candidate cannot access handoff queue
        self._auth(self.candidate_user)
        res = self.client.get("/api/v1/handoffs/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Employer cannot access handoff queue
        self._auth(self.employer_user)
        res = self.client.get("/api/v1/handoffs/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
