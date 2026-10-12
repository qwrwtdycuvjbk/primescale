import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from companies.models import Company, CompanyMember
from jobs.models import Job

User = get_user_model()


class AdminEmployerAccountControlsTest(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin_test@peopleremotely.com",
            password="AdminPass123!",
            role=User.Role.ADMIN,
            is_staff=True,
        )

        # Candidate user
        self.candidate_user = User.objects.create_user(
            email="cand_test@peopleremotely.com",
            password="CandPass123!",
            role=User.Role.CANDIDATE,
            full_name="Test Candidate",
        )

        # Employer user & company & job
        self.employer_user = User.objects.create_user(
            email="emp_ctrl@company.com",
            password="EmpPass123!",
            role=User.Role.EMPLOYER,
            full_name="Target Employer",
        )
        self.company = Company.objects.create(
            owner=self.employer_user,
            name="Acme Controls Corp",
            website="https://acmecontrols.com",
            hq_city="New York",
        )
        self.member = CompanyMember.objects.create(
            company=self.company,
            user=self.employer_user,
            member_role=CompanyMember.MemberRole.ADMIN,
        )
        self.job = Job.objects.create(
            company=self.company,
            posted_by=self.employer_user,
            title="Senior Platform Engineer",
            role_type=Job.RoleType.FULL_TIME,
            experience_level=Job.ExperienceLevel.SENIOR,
            status=Job.Status.ACTIVE,
        )

    def test_admin_deactivate_employer(self):
        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/v1/admin/employers/{self.employer_user.id}/deactivate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

        self.employer_user.refresh_from_db()
        self.assertFalse(self.employer_user.is_active)

    def test_inactive_employer_login_rejected(self):
        self.employer_user.is_active = False
        self.employer_user.save()

        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "emp_ctrl@company.com", "password": "EmpPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data.get("error"), "Your access is denied by the Admin.")

    def test_admin_activate_employer(self):
        self.employer_user.is_active = False
        self.employer_user.save()

        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/v1/admin/employers/{self.employer_user.id}/activate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

        self.employer_user.refresh_from_db()
        self.assertTrue(self.employer_user.is_active)

        # Login now succeeds
        self.client.force_authenticate(user=None)
        login_res = self.client.post(
            "/api/v1/auth/login/",
            {"email": "emp_ctrl@company.com", "password": "EmpPass123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_res.data)

    def test_admin_delete_employer_safe_cascade(self):
        self.client.force_authenticate(user=self.admin_user)
        emp_id = self.employer_user.id
        url = f"/api/v1/admin/employers/{emp_id}/delete/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Employer user and company deleted
        self.assertFalse(User.objects.filter(id=emp_id).exists())
        self.assertFalse(Company.objects.filter(id=self.company.id).exists())
        self.assertFalse(Job.objects.filter(id=self.job.id).exists())

    def test_admin_delete_employer_via_detail_endpoint(self):
        self.client.force_authenticate(user=self.admin_user)
        emp_id = self.employer_user.id
        url = f"/api/v1/admin/employers/{emp_id}/"
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(User.objects.filter(id=emp_id).exists())

    def test_non_admin_cannot_manage_employer(self):
        # Candidate cannot deactivate employer
        self.client.force_authenticate(user=self.candidate_user)
        url = f"/api/v1/admin/employers/{self.employer_user.id}/deactivate/"
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Candidate cannot delete employer
        delete_url = f"/api/v1/admin/employers/{self.employer_user.id}/delete/"
        del_res = self.client.delete(delete_url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)

        # Employer cannot delete another employer or self via admin endpoint
        self.client.force_authenticate(user=self.employer_user)
        del_res2 = self.client.delete(delete_url)
        self.assertEqual(del_res2.status_code, status.HTTP_403_FORBIDDEN)

        # Unauthenticated cannot deactivate
        self.client.force_authenticate(user=None)
        unauth_res = self.client.post(url)
        self.assertEqual(unauth_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_not_found_handling(self):
        self.client.force_authenticate(user=self.admin_user)
        random_id = uuid.uuid4()
        res = self.client.post(f"/api/v1/admin/employers/{random_id}/activate/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
