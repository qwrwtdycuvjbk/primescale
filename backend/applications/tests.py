"""
Tests for Applications and Job Leads.
Phase 17 — Applications & Job Leads Integration Tests.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import User
from companies.models import Company
from candidates.models import CandidateProfile
from jobs.models import Job
from matching.models import Match


class ApplicationsApiTests(APITestCase):
    def setUp(self):
        # Candidate 1
        self.candidate_user = User.objects.create_user(
            email="cand1@example.com",
            password="testpassword123",
            role=User.Role.CANDIDATE,
            full_name="Candidate One",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Full Stack Engineer",
            skills=["Python", "Django", "React"],
            experience_level="senior",
            open_to_matching=True,
            profile_complete=True,
        )

        # Candidate 2
        self.candidate_user2 = User.objects.create_user(
            email="cand2@example.com",
            password="testpassword123",
            role=User.Role.CANDIDATE,
            full_name="Candidate Two",
        )
        self.candidate_profile2 = CandidateProfile.objects.create(
            user=self.candidate_user2,
            headline="Frontend Engineer",
            skills=["React", "TypeScript"],
            experience_level="mid",
            open_to_matching=True,
            profile_complete=True,
        )

        # Employer 1
        self.employer_user = User.objects.create_user(
            email="emp1@example.com",
            password="testpassword123",
            role=User.Role.EMPLOYER,
            full_name="Employer One",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Tech Corp",
            country="US",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Python Engineer",
            description="We need a senior python developer.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["Python", "Django"],
            status=Job.Status.ACTIVE,
        )

        # Employer 2
        self.employer_user2 = User.objects.create_user(
            email="emp2@example.com",
            password="testpassword123",
            role=User.Role.EMPLOYER,
            full_name="Employer Two",
        )
        self.company2 = Company.objects.create(
            owner=self.employer_user2,
            name="Other Corp",
            country="US",
        )
        self.job2 = Job.objects.create(
            company=self.company2,
            posted_by=self.employer_user2,
            title="Frontend Developer",
            description="Frontend role.",
            role_type="full-time",
            experience_level="mid",
            tech_stack=["React"],
            status=Job.Status.ACTIVE,
        )

        # Admin
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
            role=User.Role.ADMIN,
            full_name="Admin User",
        )

    def test_candidate_can_apply_to_active_job(self):
        self.client.force_authenticate(user=self.candidate_user)
        response = self.client.post(
            "/api/v1/applications/apply/",
            {"job_id": str(self.job.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["ok"])
        self.assertEqual(response.data["application"]["status"], "candidate_interested")

        # Verify duplicate application is rejected
        dup_res = self.client.post(
            "/api/v1/applications/apply/",
            {"job_id": str(self.job.id)},
        )
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already applied", dup_res.data["error"])

    def test_candidate_cannot_apply_to_paused_job(self):
        self.job.status = Job.Status.PAUSED
        self.job.save()

        self.client.force_authenticate(user=self.candidate_user)
        response = self.client.post(
            "/api/v1/applications/apply/",
            {"job_id": str(self.job.id)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_role_based_access_and_idor_protection(self):
        # Candidate 1 applies
        self.client.force_authenticate(user=self.candidate_user)
        apply_res = self.client.post(
            "/api/v1/applications/apply/",
            {"job_id": str(self.job.id)},
        )
        app_id = apply_res.data["application"]["id"]

        # Candidate 1 lists applications -> sees 1
        list_res = self.client.get("/api/v1/applications/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)

        # Candidate 2 lists applications -> sees 0
        self.client.force_authenticate(user=self.candidate_user2)
        c2_list = self.client.get("/api/v1/applications/")
        self.assertEqual(c2_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(c2_list.data), 0)

        # Candidate 2 accessing Candidate 1's application detail -> 403 Forbidden
        c2_detail = self.client.get(f"/api/v1/applications/{app_id}/")
        self.assertEqual(c2_detail.status_code, status.HTTP_403_FORBIDDEN)

        # Employer 2 accessing Employer 1's job application detail -> 403 Forbidden
        self.client.force_authenticate(user=self.employer_user2)
        e2_detail = self.client.get(f"/api/v1/applications/{app_id}/")
        self.assertEqual(e2_detail.status_code, status.HTTP_403_FORBIDDEN)

        # Employer 1 lists applications -> sees Candidate 1's application
        self.client.force_authenticate(user=self.employer_user)
        e1_list = self.client.get("/api/v1/applications/")
        self.assertEqual(e1_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(e1_list.data), 1)

        # Employer 1 shortlists Candidate 1 -> triggers mutual_fit
        patch_res = self.client.patch(
            f"/api/v1/applications/{app_id}/",
            {"status": "employer_shortlisted"},
        )
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["status"], "mutual_fit")

        # Admin lists applications -> sees all
        self.client.force_authenticate(user=self.admin_user)
        admin_list = self.client.get("/api/v1/applications/")
        self.assertEqual(admin_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(admin_list.data), 1)
