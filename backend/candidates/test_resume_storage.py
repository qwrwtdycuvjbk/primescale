import io
from unittest.mock import MagicMock, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from candidates.models import CandidateProfile


class CandidateResumeStorageTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.candidate_user = User.objects.create_user(
            email="candidate1@example.com", password="password123", role=User.Role.CANDIDATE
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user, headline="Backend Engineer", skills=["Python", "Django"]
        )

        self.other_candidate = User.objects.create_user(
            email="candidate2@example.com", password="password123", role=User.Role.CANDIDATE
        )
        self.other_candidate_profile = CandidateProfile.objects.create(
            user=self.other_candidate, headline="Frontend Engineer", skills=["React"]
        )

        self.employer_user = User.objects.create_user(
            email="employer@example.com", password="password123", role=User.Role.EMPLOYER
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com", password="password123", role=User.Role.ADMIN
        )

    def _auth(self, user):
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

    def test_candidate_can_upload_own_resume_pdf(self):
        self._auth(self.candidate_user)
        pdf_file = SimpleUploadedFile("my_resume.pdf", b"%PDF-1.4 sample resume", content_type="application/pdf")

        response = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertIn("resumePath", response.data)
        self.assertIn("downloadUrl", response.data)

        self.candidate_profile.refresh_from_db()
        self.assertIsNotNone(self.candidate_profile.resume_url)
        self.assertEqual(self.candidate_profile.resume_url, response.data["resumePath"])

    def test_candidate_can_upload_own_resume_docx(self):
        self._auth(self.candidate_user)
        docx_file = SimpleUploadedFile(
            "resume.docx",
            b"PK\x03\x04 fake docx content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response = self.client.post("/api/v1/candidates/me/resume/", {"file": docx_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])

    def test_candidate_cannot_upload_disallowed_file_type(self):
        self._auth(self.candidate_user)
        exe_file = SimpleUploadedFile("script.exe", b"binary", content_type="application/x-msdownload")
        response = self.client.post("/api/v1/candidates/me/resume/", {"file": exe_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file format", response.data["error"])

    def test_candidate_cannot_upload_oversized_resume(self):
        self._auth(self.candidate_user)
        oversized = SimpleUploadedFile("huge.pdf", b"a" * (6 * 1024 * 1024), content_type="application/pdf")
        response = self.client.post("/api/v1/candidates/me/resume/", {"file": oversized}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exceeds the maximum limit", response.data["error"])

    def test_employer_cannot_upload_to_candidate_me_resume(self):
        self._auth(self.employer_user)
        pdf_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4", content_type="application/pdf")
        response = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_file}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_upload_or_download_resume(self):
        pdf_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4", content_type="application/pdf")
        post_res = self.client.post("/api/v1/candidates/me/resume/", {"file": pdf_file}, format="multipart")
        self.assertEqual(post_res.status_code, status.HTTP_401_UNAUTHORIZED)

        get_res = self.client.get("/api/v1/candidates/me/resume/")
        self.assertEqual(get_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_download_own_resume_url(self):
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/resume_123.pdf"
        self.candidate_profile.save()

        self._auth(self.candidate_user)
        response = self.client.get("/api/v1/candidates/me/resume/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["ok"])
        self.assertIn("downloadUrl", response.data)
        self.assertEqual(response.data["resumePath"], self.candidate_profile.resume_url)

    def test_candidate_download_missing_resume_404(self):
        self.candidate_profile.resume_url = None
        self.candidate_profile.save()

        self._auth(self.candidate_user)
        response = self.client.get("/api/v1/candidates/me/resume/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_download_and_upload_candidate_resume(self):
        self.candidate_profile.resume_url = f"{self.candidate_user.id}/resume_abc.pdf"
        self.candidate_profile.save()

        self._auth(self.admin_user)
        # Admin GET
        get_res = self.client.get(f"/api/v1/candidates/{self.candidate_profile.id}/resume/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertTrue(get_res.data["ok"])

        # Admin POST upload on behalf of candidate
        new_pdf = SimpleUploadedFile("admin_uploaded.pdf", b"%PDF-1.4 admin override", content_type="application/pdf")
        post_res = self.client.post(
            f"/api/v1/candidates/{self.candidate_profile.id}/resume/",
            {"file": new_pdf},
            format="multipart",
        )
        self.assertEqual(post_res.status_code, status.HTTP_200_OK)
        self.candidate_profile.refresh_from_db()
        self.assertEqual(self.candidate_profile.resume_url, post_res.data["resumePath"])

    def test_candidate_cannot_access_admin_candidate_resume_endpoint(self):
        self._auth(self.candidate_user)
        res = self.client.get(f"/api/v1/candidates/{self.other_candidate_profile.id}/resume/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
