import uuid
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from companies.models import Company
from .models import Job
from .utils import default_job_expiry, is_valid_salary_range, parse_skills


class JobUtilsTests(TestCase):
    def test_salary_validation(self):
        self.assertTrue(is_valid_salary_range("$120k - $150k"))
        self.assertTrue(is_valid_salary_range("100000 - 130000 USD"))
        self.assertFalse(is_valid_salary_range("Competitive"))
        self.assertFalse(is_valid_salary_range("DOE"))
        self.assertFalse(is_valid_salary_range("Negotiable"))
        self.assertFalse(is_valid_salary_range("TBD"))
        self.assertFalse(is_valid_salary_range("no numbers"))

    def test_job_expiry(self):
        expiry = default_job_expiry()
        now = timezone.now()
        self.assertGreater(expiry, now)
        diff_days = (expiry - now).days
        self.assertIn(diff_days, [29, 30])


class JobApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employer1 = User.objects.create_user(
            email="employer1@acme.com",
            password="Password123!",
            full_name="Acme Poster",
            role=User.Role.EMPLOYER,
        )
        self.employer2 = User.objects.create_user(
            email="employer2@beta.com",
            password="Password123!",
            full_name="Beta Poster",
            role=User.Role.EMPLOYER,
        )
        self.candidate = User.objects.create_user(
            email="candidate@test.com",
            password="Password123!",
            full_name="Alice Candidate",
            role=User.Role.CANDIDATE,
        )
        self.admin = User.objects.create_superuser(
            email="admin@peopleremotely.com",
            password="AdminPassword123!",
            full_name="Staff Admin",
        )

        self.company1 = Company.objects.create(
            owner=self.employer1,
            name="Acme Corp",
            website="https://acme.com",
            size="51-200",
            hq_city="San Francisco",
            industry="Cloud",
            profile_complete=True,
        )
        self.company2 = Company.objects.create(
            owner=self.employer2,
            name="Beta Ltd",
            website="https://beta.com",
            size="11-50",
            hq_city="New York",
            industry="Fintech",
            profile_complete=True,
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_employer_create_job_success(self):
        self._auth(self.employer1)
        payload = {
            "title": "Senior Cloud Engineer",
            "description": "Building next-gen distributed systems in Go & AWS.",
            "role_type": "full-time",
            "experience_level": "senior",
            "tech_stack": ["Go", "AWS", "Kubernetes", "Terraform"],
            "salary_range": "$140,000 - $175,000",
            "work_type": "remote",
            "visa_requirements": "US Authorized only",
            "publish": True,
        }
        res = self.client.post("/api/v1/jobs/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])
        self.assertEqual(res.data["status"], "active")

        # Verify DB object
        job = Job.objects.get(id=res.data["jobId"])
        self.assertEqual(job.company, self.company1)
        self.assertEqual(job.posted_by, self.employer1)
        self.assertIsNotNone(job.expires_at)

    def test_create_job_validation_failures(self):
        self._auth(self.employer1)
        # 1. Invalid salary
        res = self.client.post(
            "/api/v1/jobs/",
            {
                "title": "DevOps",
                "description": "Valid description",
                "role_type": "full-time",
                "experience_level": "mid",
                "tech_stack": ["AWS", "Docker", "Linux"],
                "salary_range": "Competitive",
                "visa_requirements": "US only",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("salary_range", res.data)

        # 2. Tech stack < 3 skills
        res = self.client.post(
            "/api/v1/jobs/",
            {
                "title": "DevOps",
                "description": "Valid description",
                "role_type": "full-time",
                "experience_level": "mid",
                "tech_stack": ["AWS", "Docker"],
                "salary_range": "$100k - $120k",
                "visa_requirements": "US only",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tech_stack", res.data)

    def test_job_isolation_and_update(self):
        job = Job.objects.create(
            company=self.company1,
            posted_by=self.employer1,
            title="Backend Dev",
            description="Django backend development.",
            role_type="full-time",
            experience_level="mid",
            tech_stack=["Python", "Django", "PostgreSQL"],
            salary_range="$110k - $130k",
            status="draft",
        )

        # Employer 1 updates own job -> 200
        self._auth(self.employer1)
        res = self.client.patch(f"/api/v1/jobs/{job.id}/", {"status": "active"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        job.refresh_from_db()
        self.assertEqual(job.status, "active")
        self.assertIsNotNone(job.expires_at)

        # Employer 2 tries to update Employer 1's job -> 403 Forbidden
        self._auth(self.employer2)
        res = self.client.patch(f"/api/v1/jobs/{job.id}/", {"title": "Hacked Title"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_duplication(self):
        job = Job.objects.create(
            company=self.company1,
            posted_by=self.employer1,
            title="Frontend React Lead",
            description="Lead the frontend.",
            role_type="full-time",
            experience_level="lead",
            tech_stack=["React", "TypeScript", "Next.js"],
            salary_range="$150k - $180k",
            status="active",
        )

        self._auth(self.employer1)
        res = self.client.post(f"/api/v1/jobs/{job.id}/duplicate/", format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])

        cloned_job = Job.objects.get(id=res.data["jobId"])
        self.assertEqual(cloned_job.title, "Frontend React Lead (copy)")
        self.assertEqual(cloned_job.status, "draft")
        self.assertEqual(cloned_job.company, self.company1)

    def test_public_and_filter_job_listing(self):
        Job.objects.create(
            company=self.company1,
            posted_by=self.employer1,
            title="Senior Python Architect",
            description="AI pipelines.",
            role_type="full-time",
            experience_level="senior",
            tech_stack=["Python", "PyTorch", "FastAPI"],
            salary_range="$160k - $200k",
            status="active",
        )
        Job.objects.create(
            company=self.company2,
            posted_by=self.employer2,
            title="Junior Frontend Intern",
            description="HTML and CSS.",
            role_type="contract",
            experience_level="junior",
            tech_stack=["HTML", "CSS", "JS"],
            salary_range="$50k - $60k",
            status="draft",  # Draft -> not visible to public
        )

        # Public list
        self.client.credentials()
        res = self.client.get("/api/v1/jobs/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["title"], "Senior Python Architect")

        # Public filter search
        res = self.client.get("/api/v1/jobs/?experience_level=senior")
        self.assertEqual(len(res.data), 1)

        res = self.client.get("/api/v1/jobs/?experience_level=junior")
        self.assertEqual(len(res.data), 0)
