import io
from unittest.mock import MagicMock, patch
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from common.storage import (
    ALLOWED_LOGO_TYPES,
    ALLOWED_RESUME_TYPES,
    generate_presigned_download_url,
    generate_storage_path,
    is_s3_configured,
    sanitize_filename,
    validate_file_upload,
)


class StorageFoundationUnitTests(TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("../../etc/passwd.pdf"), "passwd.pdf")
        self.assertEqual(sanitize_filename("John Doe Resume (2026).pdf"), "John_Doe_Resume__2026_.pdf")
        self.assertEqual(sanitize_filename("my-file_v1.2.docx"), "my-file_v1.2.docx")

    def test_generate_storage_path(self):
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        path = generate_storage_path(user_id, "resume.pdf")
        self.assertTrue(path.startswith(f"{user_id}/resume_"))
        self.assertTrue(path.endswith(".pdf"))

        prefixed = generate_storage_path(user_id, "logo.png", prefix="company-logos")
        self.assertTrue(prefixed.startswith(f"company-logos/{user_id}/logo_"))
        self.assertTrue(prefixed.endswith(".png"))

    def test_validate_file_upload_success(self):
        pdf_file = SimpleUploadedFile("resume.pdf", b"%PDF-1.4 test file content", content_type="application/pdf")
        # Should not raise
        validate_file_upload(pdf_file, allowed_types=ALLOWED_RESUME_TYPES, max_size_bytes=1024 * 1024)

    def test_validate_file_upload_oversized(self):
        large_content = b"x" * (2 * 1024 * 1024)
        pdf_file = SimpleUploadedFile("big.pdf", large_content, content_type="application/pdf")
        with self.assertRaises(ValidationError) as ctx:
            validate_file_upload(pdf_file, allowed_types=ALLOWED_RESUME_TYPES, max_size_bytes=1024 * 1024)
        self.assertIn("exceeds the maximum limit", str(ctx.exception))

    def test_validate_file_upload_invalid_type(self):
        exe_file = SimpleUploadedFile("script.exe", b"binarycontent", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError) as ctx:
            validate_file_upload(exe_file, allowed_types=ALLOWED_RESUME_TYPES, max_size_bytes=1024 * 1024)
        self.assertIn("Unsupported file format", str(ctx.exception))

    def test_validate_logo_file_upload_types(self):
        png_file = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        # Valid PNG should succeed
        validate_file_upload(png_file, allowed_types=ALLOWED_LOGO_TYPES, max_size_bytes=1024 * 1024)

        # PDF as logo should fail
        pdf_file = SimpleUploadedFile("logo.pdf", b"%PDF-1.4", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_file_upload(pdf_file, allowed_types=ALLOWED_LOGO_TYPES, max_size_bytes=1024 * 1024)

    @override_settings(
        AWS_ACCESS_KEY_ID="test-key",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
    )
    def test_is_s3_configured_true(self):
        self.assertTrue(is_s3_configured())

    @override_settings(
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_STORAGE_BUCKET_NAME="",
    )
    def test_is_s3_configured_false(self):
        self.assertFalse(is_s3_configured())

    @override_settings(
        AWS_ACCESS_KEY_ID="test-key",
        AWS_SECRET_ACCESS_KEY="test-secret",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
    )
    @patch("boto3.client")
    def test_generate_presigned_download_url_s3(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://test-bucket.s3.amazonaws.com/resumes/test.pdf?signature=abc"
        mock_boto_client.return_value = mock_s3

        url = generate_presigned_download_url("user-1/test.pdf", expiration=1800)
        self.assertIn("signature=abc", url)
        mock_s3.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "resumes/user-1/test.pdf"},
            ExpiresIn=1800,
        )

    @override_settings(
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_STORAGE_BUCKET_NAME="",
    )
    def test_generate_presigned_download_url_local_fallback(self):
        url = generate_presigned_download_url("user-1/test.pdf")
        self.assertEqual(url, "/media/resumes/user-1/test.pdf")
