from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from companies.models import Company, CompanyMember


class CompanyLogoStorageTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.owner_user = User.objects.create_user(
            email="owner@acme.com", password="password123", role=User.Role.EMPLOYER
        )
        self.company = Company.objects.create(
            owner=self.owner_user, name="Acme Inc", website="https://acme.com"
        )

        # Company admin member
        self.member_admin = User.objects.create_user(
            email="recruiter@acme.com", password="password123", role=User.Role.EMPLOYER
        )
        CompanyMember.objects.create(
            company=self.company, user=self.member_admin, member_role=CompanyMember.MemberRole.ADMIN
        )

        # Unaffiliated employer
        self.other_employer = User.objects.create_user(
            email="other@corp.com", password="password123", role=User.Role.EMPLOYER
        )
        self.other_company = Company.objects.create(
            owner=self.other_employer, name="Other Corp", website="https://other.com"
        )

        # Candidate user
        self.candidate_user = User.objects.create_user(
            email="candidate@example.com", password="password123", role=User.Role.CANDIDATE
        )

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin@example.com", password="password123", role=User.Role.ADMIN
        )

    def _auth(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_owner_can_upload_company_logo(self):
        self._auth(self.owner_user)
        logo = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\nfakeimage", content_type="image/png")

        res = self.client.post("/api/v1/companies/me/logo/", {"file": logo}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])
        self.assertIn("url", res.data)
        self.assertIn("logoPath", res.data)

        self.company.refresh_from_db()
        self.assertEqual(self.company.logo_url, res.data["url"])

    def test_company_admin_member_can_upload_logo_by_id(self):
        self._auth(self.member_admin)
        logo = SimpleUploadedFile("logo.jpg", b"\xff\xd8\xfffakejpg", content_type="image/jpeg")

        res = self.client.post(f"/api/v1/companies/{self.company.id}/logo/", {"file": logo}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])

        self.company.refresh_from_db()
        self.assertEqual(self.company.logo_url, res.data["url"])

    def test_unaffiliated_employer_cannot_upload_logo_for_other_company(self):
        self._auth(self.other_employer)
        logo = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")

        res = self.client.post(f"/api/v1/companies/{self.company.id}/logo/", {"file": logo}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_candidate_cannot_upload_company_logo(self):
        self._auth(self.candidate_user)
        logo = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")

        res = self.client.post(f"/api/v1/companies/{self.company.id}/logo/", {"file": logo}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_upload_company_logo(self):
        self._auth(self.admin_user)
        logo = SimpleUploadedFile("admin_logo.webp", b"RIFFfakeWEBP", content_type="image/webp")

        res = self.client.post(f"/api/v1/companies/{self.company.id}/logo/", {"file": logo}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["ok"])

    def test_invalid_logo_file_type_rejected(self):
        self._auth(self.owner_user)
        pdf = SimpleUploadedFile("not_a_logo.pdf", b"%PDF-1.4", content_type="application/pdf")

        res = self.client.post("/api/v1/companies/me/logo/", {"file": pdf}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file format", res.data["error"])

    def test_oversized_logo_file_rejected(self):
        self._auth(self.owner_user)
        oversized = SimpleUploadedFile("large_logo.png", b"x" * (3 * 1024 * 1024), content_type="image/png")

        res = self.client.post("/api/v1/companies/me/logo/", {"file": oversized}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds the maximum limit", res.data["error"])
