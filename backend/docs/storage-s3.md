# Phase 6 — AWS S3 & File Storage Migration Foundation Documentation

## 1. Overview
In Phase 6, we implemented the AWS S3 and file storage foundation in the Django REST Framework backend.

> **CRITICAL ARCHITECTURAL SAFETY NOTE:**
> Existing Supabase Storage remains fully active and untouched in production.
> **0 production files have been migrated or deleted.**
> **0 Supabase database records or policies have been modified.**
> **0 Next.js frontend files have been modified.**

---

## 2. Storage Architecture

```
                                 ┌───────────────────────────┐
                                 │       Next.js Client      │
                                 └─────────────┬─────────────┘
                                               │ (Multipart Upload / Presigned GET)
                                               ▼
                                 ┌───────────────────────────┐
                                 │   Django REST Framework   │
                                 │   - Auth & Permissions    │
                                 │   - File Validation       │
                                 │   - Key Generation        │
                                 └─────────────┬─────────────┘
                                               │
                        ┌──────────────────────┴──────────────────────┐
                        ▼                                             ▼
          ┌───────────────────────────┐                 ┌───────────────────────────┐
          │    PublicMediaStorage     │                 │    PrivateMediaStorage    │
          │    (e.g., Company Logos)  │                 │    (e.g., Resumes)        │
          │    Location: company-logos│                 │    Location: resumes/     │
          │    ACL: public-read       │                 │    ACL: private           │
          └─────────────┬─────────────┘                 └─────────────┬─────────────┘
                        │                                             │
                        │ Direct Public URL                           │ 1-Hour Presigned URL
                        ▼                                             ▼
                 AWS S3 / CDN Bucket                           AWS S3 Private Bucket
```

---

## 3. Storage Paths and Separation

### Candidate Resumes (Private)
- **Storage Path**: `resumes/{user_id}/{sanitized_filename}_{token}.{ext}`
- **Permissions**: Strictly private. Direct object access blocked.
- **Allowed Types**: PDF, DOC, DOCX (`application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
- **Max File Size**: 5 MB (`MAX_RESUME_SIZE_BYTES`).
- **Access Method**: Authenticated candidates can generate a **1-hour temporary presigned URL** for their own resume via `GET /api/v1/candidates/me/resume/`. Admins can access via `GET /api/v1/candidates/<candidate_id>/resume/`.

### Company Logos (Public)
- **Storage Path**: `company-logos/{company_id}/{sanitized_filename}_{token}.{ext}`
- **Permissions**: Publicly readable directly or via CDN / custom domain.
- **Allowed Types**: JPEG, PNG, WebP, SVG (`image/jpeg`, `image/png`, `image/webp`, `image/svg+xml`).
- **Max File Size**: 2 MB (`MAX_LOGO_SIZE_BYTES`).
- **Access Method**: Public URL saved directly to `Company.logo_url`.
- **Upload Restrictions**: Only company owners, company member admins/recruiters, or platform administrators can upload logos.

---

## 4. Endpoints Implemented

| Endpoint | Method | Allowed Roles | Description |
|---|---|---|---|
| `/api/v1/candidates/me/resume/` | `GET` | Candidate, Admin | Get temporary presigned download URL for own resume |
| `/api/v1/candidates/me/resume/` | `POST` | Candidate, Admin | Upload resume file (PDF/DOCX) |
| `/api/v1/candidates/<uuid:pk>/resume/` | `GET` | Admin | Get temporary presigned download URL for any candidate's resume |
| `/api/v1/candidates/<uuid:pk>/resume/` | `POST` | Admin | Upload resume file on behalf of a candidate |
| `/api/v1/companies/me/logo/` | `POST` | Employer Owner, Admin | Upload company logo (PNG/JPG/WebP/SVG) |
| `/api/v1/companies/<uuid:pk>/logo/` | `POST` | Company Member (Admin/Recruiter), Owner, Platform Admin | Upload company logo by company ID |

---

## 5. Local Development and Fallback Behavior
- When `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_STORAGE_BUCKET_NAME` are not provided, the storage system seamlessly falls back to Django's local `FileSystemStorage` (`MEDIA_ROOT` = `backend/media/`).
- Unit tests run completely offline without contacting AWS or needing real AWS credentials.
- In production, when environment variables are supplied, `django-storages` and `boto3` connect securely to the target S3 bucket.

---

## 6. Environment Variables Required

| Variable | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | AWS IAM Access Key | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM Secret Key | `secret...` |
| `AWS_STORAGE_BUCKET_NAME` | Name of the AWS S3 Bucket | `people-remotely-storage` |
| `AWS_S3_REGION_NAME` | AWS Region | `us-east-1` |
| `AWS_S3_CUSTOM_DOMAIN` | Optional CloudFront or custom domain | `cdn.peopleremotely.com` |

---

## 7. Future Supabase Storage Migration Path (Phase 7+)
Once Next.js is fully migrated to use the Django REST API in subsequent phases:
1. An offline migration script (`python manage.py migrate_supabase_storage_to_s3`) will query the existing Supabase storage buckets (`resumes`, `company-logos`).
2. Stream files from Supabase Storage into the AWS S3 bucket under the corresponding Django storage paths.
3. Update `resume_url` and `logo_url` records in PostgreSQL.
4. Verify all files and signatures.
5. Decommission Supabase Storage buckets.
