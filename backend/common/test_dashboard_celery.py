"""
Unit tests for Admin Dashboard Analytics View & Celery Task Verification.
Phase 18 — Admin Dashboard Analytics & Background Services / Celery.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import User
from companies.models import Company
from candidates.models import CandidateProfile
from jobs.models import Job
from matching.models import Match
from handoffs.models import HandoffRequest
from matching.tasks import run_matching_for_candidate_task, run_matching_for_job_task
from accounts.tasks import send_password_reset_email_task, send_verification_email_task


class AdminDashboardAnalyticsTests(APITestCase):
    def setUp(self):
        # Admin user
        self.admin_user = User.objects.create_superuser(
            email="admin_analytics@example.com",
            password="adminpassword123",
            role=User.Role.ADMIN,
            full_name="Admin Ops",
        )

        # Candidate user & profile
        self.candidate_user = User.objects.create_user(
            email="cand_analytics@example.com",
            password="candpassword123",
            role=User.Role.CANDIDATE,
            full_name="Jane Doe",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Senior Python Engineer",
            skills=["python", "django", "postgresql"],
            experience_level="senior",
            years_experience=6,
            work_authorization="us_citizen",
            profile_complete=True,
            open_to_matching=True,
        )

        # Incomplete candidate
        self.incomplete_user = User.objects.create_user(
            email="incomplete@example.com",
            password="password123",
            role=User.Role.CANDIDATE,
            full_name="Incomplete Candidate",
        )
        self.incomplete_profile = CandidateProfile.objects.create(
            user=self.incomplete_user,
            profile_complete=False,
        )

        # Employer user, company, & jobs
        self.employer_user = User.objects.create_user(
            email="emp_analytics@example.com",
            password="emppassword123",
            role=User.Role.EMPLOYER,
            full_name="John Recruiter",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Analytics Corp",
            country="US",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Architect",
            description="Leading backend systems.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["python", "django", "postgresql"],
            status=Job.Status.ACTIVE,
        )

        # Unmatched job
        self.unmatched_job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="DevOps Lead",
            description="Kubernetes & Terraform specialist.",
            role_type="full-time",
            experience_level="lead",
            tech_stack=["kubernetes", "terraform", "aws"],
            status=Job.Status.ACTIVE,
        )

        # Match & Handoff
        self.match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=95,
            status=Match.Status.MUTUAL_FIT,
            visible_to_employer=True,
        )
        self.handoff = HandoffRequest.objects.create(
            match=self.match,
            status=HandoffRequest.Status.PENDING,
        )

    def test_admin_can_retrieve_dashboard_stats(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/v1/admin/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIn("pendingMatches", data)
        self.assertIn("pendingHandoffs", data)
        self.assertIn("newCandidatesThisWeek", data)
        self.assertIn("newEmployersThisWeek", data)
        self.assertIn("activeJobsWithNoMatches", data)
        self.assertIn("incompleteProfiles", data)

        # Verify values
        self.assertGreaterEqual(data["newCandidatesThisWeek"], 2)
        self.assertGreaterEqual(data["newEmployersThisWeek"], 1)
        self.assertEqual(data["pendingHandoffs"], 1)
        self.assertEqual(data["activeJobsWithNoMatches"], 1)
        self.assertEqual(len(data["unmatchedJobPreviews"]), 1)
        self.assertEqual(data["unmatchedJobPreviews"][0]["title"], "DevOps Lead")

    def test_candidate_forbidden_from_dashboard_stats(self):
        self.client.force_authenticate(user=self.candidate_user)
        response = self.client.get("/api/v1/admin/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employer_forbidden_from_dashboard_stats(self):
        self.client.force_authenticate(user=self.employer_user)
        response = self.client.get("/api/v1/admin/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected_from_dashboard_stats(self):
        response = self.client.get("/api/v1/admin/dashboard/stats/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_celery_matching_tasks_execution(self):
        # Verify candidate matching task executes cleanly
        result = run_matching_for_candidate_task(str(self.candidate_profile.id))
        self.assertIn("matched", result)

        # Verify job matching task executes cleanly
        job_result = run_matching_for_job_task(str(self.job.id))
        self.assertIn("matched", job_result)

    def test_celery_email_tasks_execution(self):
        # Verify password reset email task dispatches cleanly through test backend
        reset_result = send_password_reset_email_task("test_reset@example.com", "uid123", "token123")
        self.assertTrue(reset_result)

        # Verify verification email task dispatches cleanly through test backend
        verify_result = send_verification_email_task("test_verify@example.com", "uid123", "token123")
        self.assertTrue(verify_result)
