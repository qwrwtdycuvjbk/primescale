import os
import re
import uuid
import mimetypes
from django.conf import settings
from django.core.files.storage import default_storage, FileSystemStorage
from rest_framework.exceptions import ValidationError

try:
    from storages.backends.s3boto3 import S3Boto3Storage
except ImportError:
    S3Boto3Storage = None


# MIME types & extension specifications
ALLOWED_RESUME_TYPES = {
    "application/pdf": [".pdf"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
}

ALLOWED_LOGO_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "image/svg+xml": [".svg"],
}


class PublicMediaStorage(S3Boto3Storage if S3Boto3Storage else FileSystemStorage):
    """
    Storage class for publicly accessible media such as company logos.
    """
    location = "company-logos"
    default_acl = "public-read"
    file_overwrite = False
    custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None) or None


class PrivateMediaStorage(S3Boto3Storage if S3Boto3Storage else FileSystemStorage):
    """
    Storage class for private media such as candidate resumes.
    Never publicly readable. Access is managed via presigned URLs.
    """
    location = "resumes"
    default_acl = "private"
    file_overwrite = False
    custom_domain = False
    querystring_auth = True


def is_s3_configured() -> bool:
    """
    Checks if AWS S3 credentials and bucket name are fully configured.
    """
    return bool(
        getattr(settings, "AWS_ACCESS_KEY_ID", "")
        and getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        and getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    )


def get_public_storage():
    """
    Returns public storage engine (S3 if configured, else local FileSystemStorage).
    """
    if is_s3_configured() and S3Boto3Storage:
        return PublicMediaStorage()
    return FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "company-logos"),
        base_url=f"{settings.MEDIA_URL}company-logos/",
    )


def get_private_storage():
    """
    Returns private storage engine (S3 if configured, else local FileSystemStorage).
    """
    if is_s3_configured() and S3Boto3Storage:
        return PrivateMediaStorage()
    return FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, "resumes"),
        base_url=f"{settings.MEDIA_URL}resumes/",
    )


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes filename by stripping path traversals, non-alphanumeric characters (except dots/hyphens).
    """
    # Strip any directory components
    clean_name = os.path.basename(filename)
    # Remove potentially unsafe characters
    clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", clean_name)
    return clean_name


def generate_storage_path(resource_id: str, original_filename: str, prefix: str = "") -> str:
    """
    Generates a secure, collision-free storage path:
    Format: {resource_id}/{unique_token}_{sanitized_filename}
    """
    sanitized = sanitize_filename(original_filename)
    unique_token = uuid.uuid4().hex[:8]
    ext = os.path.splitext(sanitized)[1].lower()
    base = os.path.splitext(sanitized)[0]
    filename = f"{base}_{unique_token}{ext}" if base else f"file_{unique_token}{ext}"
    if prefix:
        return f"{prefix}/{resource_id}/{filename}"
    return f"{resource_id}/{filename}"


def validate_file_upload(file_obj, allowed_types: dict, max_size_bytes: int):
    """
    Validates uploaded file size, extension, and content type.
    """
    if not file_obj:
        raise ValidationError("No file provided.")

    # Size check
    if file_obj.size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise ValidationError(f"File size exceeds the maximum limit of {max_mb:.1f} MB.")

    # Content type & extension check
    content_type = getattr(file_obj, "content_type", "")
    filename = file_obj.name or ""
    ext = os.path.splitext(filename)[1].lower()

    # Determine guessed MIME type as secondary check
    guessed_type, _ = mimetypes.guess_type(filename)

    # Check if content_type matches any allowed type
    is_allowed = False
    for mime, extensions in allowed_types.items():
        if content_type == mime or (guessed_type == mime):
            if ext in extensions:
                is_allowed = True
                break

    if not is_allowed:
        allowed_exts = ", ".join(sorted({ext for exts in allowed_types.values() for ext in exts}))
        raise ValidationError(f"Unsupported file format '{ext}'. Allowed formats: {allowed_exts}.")


def generate_presigned_download_url(storage_path: str, expiration: int = None) -> str:
    """
    Generates a presigned download URL for a private storage key.
    If S3 is active, calls boto3 S3 client to generate presigned GET url.
    If local storage is active, returns local media URL or test URL.
    """
    if expiration is None:
        expiration = getattr(settings, "RESUME_PRESIGNED_EXPIRATION", 3600)

    if is_s3_configured():
        import boto3
        from botocore.config import Config

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(signature_version=settings.AWS_S3_SIGNATURE_VERSION),
        )

        # Storage path may or may not have prefix 'resumes/'
        key = storage_path.lstrip("/")
        if not key.startswith("resumes/") and not key.startswith("company-logos/"):
            key = f"resumes/{key}"

        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": key,
            },
            ExpiresIn=expiration,
        )
        return presigned_url

    # Local fallback for development/testing
    clean_path = storage_path.lstrip("/")
    return f"{settings.MEDIA_URL}resumes/{clean_path}"
