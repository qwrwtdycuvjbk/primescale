"""
Tests for Job Leads and Role Submissions API.
Phase 17 — Job Leads API tests.
Phase 21 — Role Submissions API tests.
"""

from rest_framework.test import APITestCase
from rest_framework import status
from accounts.models import User
from job_leads.models import JobLead, RoleSubmission


class JobLeadsApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123",
            role=User.Role.ADMIN,
            full_name="Admin User",
        )
        self.candidate_user = User.objects.create_user(
            email="cand@example.com",
            password="testpassword123",
            role=User.Role.CANDIDATE,
            full_name="Candidate User",
        )
        self.lead = JobLead.objects.create(
            external_id="lead_123",
            title="Remote Senior Backend Engineer",
            company="Global Tech",
            apply_url="https://example.com/apply",
            country="GB",
            location="London, UK",
            is_remote=True,
        )

    def test_admin_can_list_and_create_job_leads(self):
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get("/api/v1/job-leads/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["leads"][0]["title"], "Remote Senior Backend Engineer")

    def test_non_admin_forbidden_from_job_leads(self):
        self.client.force_authenticate(user=self.candidate_user)
        res = self.client.get("/api/v1/job-leads/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class RoleSubmissionsApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin_roles@example.com",
            password="adminpassword123",
            role=User.Role.ADMIN,
            full_name="Admin Roles",
        )
        self.candidate_user = User.objects.create_user(
            email="cand_roles@example.com",
            password="testpassword123",
            role=User.Role.CANDIDATE,
            full_name="Candidate Roles",
        )

    def test_anonymous_can_submit_role(self):
        payload = {
            "companyName": "Acme Corp",
            "contactName": "Alice Smith",
            "email": "ALICE@acmecorp.com",
            "phone": "+1 555-0199",
            "jobTitle": "Lead Python Developer",
            "roleType": "Full-time",
            "experienceLevel": "senior",
            "techStack": "Python, Django, PostgreSQL",
            "salaryRange": "$140k-$170k",
            "description": "Building scalable backend services.",
            "notes": "Fast hiring process.",
            "submissionType": "company_submission",
        }
        res = self.client.post("/api/v1/role-submissions/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])
        self.assertIn("id", res.data["data"])
        self.assertEqual(res.data["data"]["email"], "alice@acmecorp.com")
        self.assertEqual(RoleSubmission.objects.count(), 1)
        sub = RoleSubmission.objects.first()
        self.assertEqual(sub.company_name, "Acme Corp")
        self.assertEqual(sub.job_title, "Lead Python Developer")

    def test_admin_can_list_role_submissions(self):
        RoleSubmission.objects.create(
            company_name="Beta LLC",
            job_title="DevOps Engineer",
            email="ops@beta.com",
        )
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get("/api/v1/role-submissions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])
        self.assertGreaterEqual(res.data["count"], 1)
        self.assertTrue(any(s["company_name"] == "Beta LLC" for s in res.data["submissions"]))

    def test_non_admin_cannot_list_role_submissions(self):
        self.client.force_authenticate(user=self.candidate_user)
        res = self.client.get("/api/v1/role-submissions/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
