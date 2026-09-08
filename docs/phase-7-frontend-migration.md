# Phase 7 — Next.js → Django REST API Migration Tracker

| Feature / Domain | Sub-Feature | Supabase Service | Django Endpoint | Frontend Status | Verification | Phase 7 Status |
|---|---|---|---|---|---|---|
| **Public Showcase** | Public Talent Cards | DB (`candidate_profiles`) | `GET /api/v1/candidates/public-showcase/` | CONNECTED | TESTED | MIGRATED |
| **API Client** | Centralized API Layer | N/A | `DJANGO_API_URL` foundation | CONNECTED | TESTED | MIGRATED |
| **Jobs** | Create Job | DB (`jobs`) | `POST /api/v1/jobs/` | CONNECTED | TESTED | MIGRATED |
| **Jobs** | Update Job Status | DB (`jobs`) | `PATCH /api/v1/jobs/<id>/` | CONNECTED | TESTED | MIGRATED |
| **Jobs** | Duplicate Job | DB (`jobs`) | `POST /api/v1/jobs/<id>/duplicate/` | CONNECTED | TESTED | MIGRATED |
| **Companies** | Save / Update Company | DB (`companies`) | `POST /api/v1/companies/me/` | CONNECTED | TESTED | MIGRATED |
| **Storage (Logos)**| Company Logo Upload | Storage (`company-logos`) | `POST /api/v1/companies/me/logo/` | CONNECTED | TESTED | MIGRATED |
| **Candidates** | Save / Update Profile | DB (`candidate_profiles`)| `POST /api/v1/candidates/me/` | CONNECTED | TESTED | MIGRATED |
| **Storage (Resumes)**| Resume Upload & Presign | Storage (`resumes`) | `POST/GET /api/v1/candidates/me/resume/` | CONNECTED | TESTED | MIGRATED |
| **Matches** | Update Match Status | DB (`matches`) | `PATCH /api/v1/matches/<id>/` | CONNECTED | TESTED | MIGRATED |
| **Handoffs** | Update Handoff Status | DB (`handoff_requests`) | `PATCH /api/v1/handoffs/<id>/` | CONNECTED | TESTED | MIGRATED |
| **Authentication** | Login, Signup, Session, OAuth | Supabase Auth | `POST /api/v1/auth/*` (ready) | NOT MIGRATED (Retained) | NOT MIGRATED | RETAINED ON SUPABASE |
| **AI Matching** | OpenAI JD & Score Parsing | OpenAI | Deferred | DEFERRED | N/A | DEFERRED |
| **External Leads** | JSearch / OpenWeb Ninja | RapidAPI | Deferred | DEFERRED | N/A | DEFERRED |
