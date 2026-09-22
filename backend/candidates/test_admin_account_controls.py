import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from candidates.models import CandidateProfile
from companies.models import Company
from jobs.models import Job
from matching.models import Match

User = get_user_model()


class AdminAccountControlsTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin_test@peopleremotely.com",
            password="AdminPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )

        # Active candidate with full name and email
        self.candidate_user = User.objects.create_user(
            email="active_cand@test.com",
            password="CandPass123!",
            role=User.Role.CANDIDATE,
            full_name="Active Candidate",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            headline="Fullstack Developer",
        )

        # Candidate with single name
        self.single_name_cand = User.objects.create_user(
            email="vamshi@gmail.com",
            password="CandPass123!",
            role=User.Role.CANDIDATE,
            full_name="Vamshi",
        )
        self.single_name_profile = CandidateProfile.objects.create(
            user=self.single_name_cand,
            headline="Backend Developer",
        )

        # Employer user & company & job
        self.employer_user = User.objects.create_user(
            email="emp_test@company.com",
            password="EmpPass123!",
            role=User.Role.EMPLOYER,
            full_name="Tech Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Acme Corp",
            website="https://acme.com",
            hq_city="San Francisco",
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Engineer",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.ACTIVE,
        )
        self.match = Match.objects.create(
            candidate_profile=self.candidate_profile,
            job=self.job,
            match_score=85,
        )

    def test_admin_candidate_list_real_identity(self):
        self.client.force_authenticate(user=self.admin_user)
        url = "/api/v1/admin/candidates/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("candidates", response.data)

        candidates = {c["id"]: c for c in response.data["candidates"]}
        cand1 = candidates.get(str(self.candidate_profile.id))
        self.assertIsNotNone(cand1)
        self.assertEqual(cand1["user_full_name"], "Active Candidate")
        self.assertEqual(cand1["full_name"], "Active Candidate")
        self.assertEqual(cand1["name"], "Active Candidate")
        self.assertEqual(cand1["user_email"], "active_cand@test.com")
        self.assertEqual(cand1["email"], "active_cand@test.com")
        self.assertTrue(cand1["user_is_active"])

        cand2 = candidates.get(str(self.single_name_profile.id))
        self.assertIsNotNone(cand2)
        self.assertEqual(cand2["user_full_name"], "Vamshi")
        self.assertEqual(cand2["name"], "Vamshi")
        self.assertEqual(cand2["user_email"], "vamshi@gmail.com")

    def test_admin_candidate_detail_real_identity(self):
        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/v1/candidates/{self.candidate_profile.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_full_name"], "Active Candidate")
        self.assertEqual(response.data["user_email"], "active_cand@test.com")
        self.assertEqual(response.data["name"], "Active Candidate")
        self.assertEqual(response.data["email"], "active_cand@test.com")
        self.assertTrue(response.data["user_is_active"])

    def test_admin_deactivate_candidate(self):
        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/v1/admin/candidates/{self.candidate_profile.id}/deactivate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        self.candidate_user.refresh_from_db()
        self.assertFalse(self.candidate_user.is_active)

    def test_inactive_candidate_login_rejected(self):
        # Deactivate candidate
        self.candidate_user.is_active = False
        self.candidate_user.save()

        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "active_cand@test.com", "password": "CandPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("error"), "Your access is denied by the Admin.")
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_inactive_candidate_google_login_rejected(self):
        self.candidate_user.is_active = False
        self.candidate_user.save()

        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/auth/oauth/google/",
            {"email": "active_cand@test.com", "role": "candidate"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("error"), "Your access is denied by the Admin.")

    def test_admin_activate_candidate(self):
        self.candidate_user.is_active = False
        self.candidate_user.save()

        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/v1/admin/candidates/{self.candidate_profile.id}/activate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

        self.candidate_user.refresh_from_db()
        self.assertTrue(self.candidate_user.is_active)

        # Login now succeeds
        self.client.force_authenticate(user=None)
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "active_cand@test.com", "password": "CandPass123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_res.data)

    def test_admin_delete_candidate_safe_cascade(self):
        self.client.force_authenticate(user=self.admin_user)
        cand_id = self.candidate_profile.id
        url = f"/api/v1/admin/candidates/{cand_id}/delete/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Candidate user and profile deleted
        self.assertFalse(User.objects.filter(id=self.candidate_user.id).exists())
        self.assertFalse(CandidateProfile.objects.filter(id=cand_id).exists())
        # Matches deleted
        self.assertFalse(Match.objects.filter(id=self.match.id).exists())
        # Job and company preserved
        self.assertTrue(Job.objects.filter(id=self.job.id).exists())
        self.assertTrue(Company.objects.filter(id=self.company.id).exists())
        self.assertTrue(User.objects.filter(id=self.employer_user.id).exists())

    def test_non_admin_cannot_manage_candidate_account(self):
        # Candidate cannot deactivate self or others
        self.client.force_authenticate(user=self.candidate_user)
        url = f"/api/v1/admin/candidates/{self.candidate_profile.id}/deactivate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Employer cannot delete candidate
        self.client.force_authenticate(user=self.employer_user)
        delete_url = f"/api/v1/admin/candidates/{self.candidate_profile.id}/delete/"
        delete_res = self.client.delete(delete_url)
        self.assertEqual(delete_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_read_only_employers(self):
        self.client.force_authenticate(user=self.admin_user)
        url = "/api/v1/admin/employers/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("employers", response.data)
        self.assertGreaterEqual(response.data["totalCount"], 1)

        # Mutations forbidden
        post_res = self.client.post(url, {"name": "New Co"})
        self.assertEqual(post_res.status_code, status.HTTP_403_FORBIDDEN)