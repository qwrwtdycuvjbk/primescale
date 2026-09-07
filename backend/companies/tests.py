import uuid
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from .models import Company, CompanyMember
from .utils import extract_email_domain, extract_website_domain, is_work_email_domain_verified


class CompanyUtilsTests(TestCase):
    def test_domain_extraction(self):
        self.assertEqual(extract_email_domain("john@acme.com"), "acme.com")
        self.assertEqual(extract_website_domain("https://acme.com"), "acme.com")
        self.assertEqual(extract_website_domain("https://www.acme.com"), "acme.com")
        self.assertEqual(extract_website_domain("http://sub.acme.com"), "sub.acme.com")

    def test_domain_verification(self):
        self.assertTrue(is_work_email_domain_verified("alice@stripe.com", "https://stripe.com"))
        self.assertTrue(is_work_email_domain_verified("alice@uk.stripe.com", "https://stripe.com"))
        self.assertFalse(is_work_email_domain_verified("alice@gmail.com", "https://stripe.com"))
        self.assertFalse(is_work_email_domain_verified("alice@stripe.com", ""))


class CompanyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employer1 = User.objects.create_user(
            email="employer1@acme.com",
            password="Password123!",
            full_name="Acme Employer",
            role=User.Role.EMPLOYER,
        )
        self.employer2 = User.objects.create_user(
            email="employer2@beta.com",
            password="Password123!",
            full_name="Beta Employer",
            role=User.Role.EMPLOYER,
        )
        self.candidate = User.objects.create_user(
            email="candidate@test.com",
            password="Password123!",
            full_name="Test Candidate",
            role=User.Role.CANDIDATE,
        )
        self.admin = User.objects.create_superuser(
            email="admin@peopleremotely.com",
            password="AdminPassword123!",
            full_name="Admin Staff",
        )

    def _auth(self, user):
        token = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_company_success(self):
        self._auth(self.employer1)
        payload = {
            "name": "Acme Corp",
            "website": "https://acme.com",
            "size": "51-200",
            "description": "Leading developer tooling company.",
            "hq_city": "San Francisco",
            "industry": "Software",
            "badge_remote_first": True,
        }
        res = self.client.post("/api/v1/companies/me/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["ok"])
        self.assertTrue(res.data["domainVerified"])
        self.assertTrue(res.data["profileComplete"])

        # Check membership auto-creation
        company = Company.objects.get(id=res.data["companyId"])
        self.assertTrue(CompanyMember.objects.filter(company=company, user=self.employer1, member_role="admin").exists())

    def test_candidate_cannot_create_company(self):
        self._auth(self.candidate)
        payload = {"name": "Candidate Corp"}
        res = self.client.post("/api/v1/companies/me/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_and_update_own_company(self):
        company = Company.objects.create(
            owner=self.employer1,
            name="Acme Inc",
            website="https://acme.com",
            size="11-50",
            description="Tech company",
            hq_city="Austin",
            industry="IT",
            domain_verified=True,
            profile_complete=True,
        )
        self._auth(self.employer1)

        # GET /me
        res = self.client.get("/api/v1/companies/me/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "Acme Inc")

        # PATCH /me
        res = self.client.patch("/api/v1/companies/me/", {"hq_city": "New York"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["hq_city"], "New York")

    def test_employer_isolation(self):
        company1 = Company.objects.create(
            owner=self.employer1,
            name="Acme Inc",
            website="https://acme.com",
        )
        self._auth(self.employer2)

        # Employer2 calls /me -> 404 because they don't own company1
        res = self.client.get("/api/v1/companies/me/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_public_company_detail(self):
        company = Company.objects.create(
            owner=self.employer1,
            name="Acme Inc",
            website="https://acme.com",
            size="11-50",
            hq_city="Austin",
            industry="IT",
        )
        # Unauthenticated request
        self.client.credentials()
        res = self.client.get(f"/api/v1/companies/{company.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "Acme Inc")
        self.assertNotIn("owner_email", res.data)

    def test_company_members_management(self):
        company = Company.objects.create(
            owner=self.employer1,
            name="Acme Inc",
        )
        CompanyMember.objects.create(company=company, user=self.employer1, member_role="admin")

        # Employer1 adds member
        self._auth(self.employer1)
        res = self.client.post(
            f"/api/v1/companies/{company.id}/members/",
            {"user_id": str(self.candidate.id), "member_role": "recruiter"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Employer2 tries to add member to company1 -> 403 Forbidden
        self._auth(self.employer2)
        res = self.client.post(
            f"/api/v1/companies/{company.id}/members/",
            {"user_id": str(self.candidate.id)},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
