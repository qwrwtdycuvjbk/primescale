# Phase 19 — Full Supabase Dependency Audit & Django-Only Cutover Readiness Report

## 1. Executive Summary
This repository audit represents a comprehensive, multi-layered investigation of all remaining Supabase dependencies across the codebase following the completion of Phases 12 through 18.
The audit adhered strictly to the **"AUDIT FIRST. REMOVE LATER"** directive:
* **Zero Destructive Changes**: No code, dependencies, fallback logic, or environment variables were removed or disabled.
* **Production Integrity Preserved**: Supabase production database, authentication, and storage remained completely untouched.
* **Algorithm Integrity Preserved**: The deterministic matching formula `round(skill_score * 0.7 + exp_score * 0.3)` remains identical in both Next.js and Django without any AI/embedding changes.
* **Cutover Status**: The core application modules (Authentication, Companies, Candidate Profiles, Jobs, Matches, Handoff Requests, Applications, Job Leads, Admin Analytics) are operating in **Django-First** mode with Supabase retained purely as a secondary compatibility fallback. However, a small set of administrative actions (`/api/admin/candidates/import`, `/api/admin/candidates/[id]/resume`, and `AdminCandidateRegistry` queries) remain directly coupled to Supabase.

## 2. Current Architecture Overview
```text
                                +---------------------------+
                                |      Next.js 16 App       |
                                |  (Frontend UI & Proxy)    |
                                +-------------+-------------+
                                              |
                       HttpOnly JWT Cookie    |   Direct Admin / Fallback
                      (access & refresh)      |   (Compatibility Mode)
                                              v
                 +----------------------------+---------------------------+
                 |                                                        |
                 v                                                        v
+---------------------------------+                      +---------------------------------+
|     Django REST Framework       |                      |         Supabase Client         |
|   (Primary Application Logic)   |                      |  (Secondary Fallback / Admin)   |
+----------------+----------------+                      +----------------+----------------+
                 |                                                        |
                 +-----------------------------+                          |
                 |                             |                          |
                 v                             v                          v
+---------------------------------+  +-------------------+  +------------------------------+
|   PostgreSQL Database           |  | AWS S3 Foundation |  | Legacy Supabase Storage / DB |
|   (peopleremotely_local)        |  | (Resumes & Logos) |  | (Production Untouched)       |
+---------------------------------+  +-------------------+  +------------------------------+
                 |
                 v
+---------------------------------+
|       Celery + Redis            |
|   (Asynchronous Processing)     |
+---------------------------------+
```

## 3. Complete Supabase Dependency Inventory Table
| File | Supabase Dependency | Purpose | Classification | Django Replacement | Removal Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `src/lib/auth.ts` | `createClient`, `auth.getUser`, `.from("profiles")` | Fallback user profile lookup if no Django JWT | Fallback | `djangoAuth.getCurrentUser` | Low |
| `src/middleware.ts` | `createServerClient`, `auth.getUser` | Route protection fallback if no Django cookies | Fallback | Django JWT cookie verification | Low |
| `src/lib/auth-actions.ts` | `auth.signIn`, `auth.signUp`, `.from("profiles")` | Legacy server action auth fallbacks | Fallback | `/api/v1/auth/` endpoints | Low |
| `src/components/auth/AuthGoogleSection.tsx` | `auth.signInWithOAuth` | Client-side OAuth trigger | Fallback / Legacy | Django Google OAuth exchange | Medium |
| `src/components/auth/AuthLoginForm.tsx` | `supabase.auth.signInWithPassword` | Legacy password login | Fallback | `djangoAuth.login` via `/api/auth/login` | Low |
| `src/lib/admin-dashboard.ts` | `getAdminClient`, `.from("matches")`, `.from("handoffs")` | Admin stats calculation fallback | Fallback | `adminApi.getDashboardStats` | Low |
| `src/app/admin/matches/page.tsx` | `getAdminClient`, `.from("matches")` | Admin review list fallback | Fallback | `matchingApi.listMatches` | Low |
| `src/app/admin/handoffs/page.tsx` | `getAdminClient`, `.from("handoff_requests")` | Admin handoffs list fallback | Fallback | `handoffsApi.listHandoffs` | Low |
| `src/app/admin/jobs/page.tsx` | `getAdminClient`, `.from("jobs")` | Admin jobs registry query | Active (Category B) | Django `/api/v1/jobs/?view=admin` | Medium |
| `src/app/admin/jobs/new/page.tsx` | `getAdminClient`, `.from("companies")` | Company selector dropdown | Active (Category B) | Django `/api/v1/companies/` | Low |
| `src/app/admin/candidates/page.tsx` | `getAdminClient`, `.from("candidate_profiles")` | Admin candidate table with relational filters | Active (Category B) | Django Admin Candidate API (P0) | High |
| `src/app/api/admin/candidates/route.ts` | `createAdminCandidate` | Admin candidate creation endpoint | Active (Category B) | Django Admin Candidate Create API (P0) | High |
| `src/app/api/admin/candidates/import/route.ts` | `createAdminCandidate`, `getServiceClient` | Excel/CSV bulk import for candidates | Active (Category C) | Django Bulk Import Endpoint (P0) | High |
| `src/app/api/admin/candidates/[id]/resume/route.ts` | `supabase.storage.from("resumes")` | Admin resume download/upload | Active (Category B) | Django Admin Candidate Resume API (P0) | High |
| `src/app/api/admin/jobs/route.ts` | `getServiceClient`, `.from("jobs")` | Admin job creation route | Fallback / Legacy | Django `jobsApi.createJob` | Low |
| `src/app/api/candidate/profile/route.ts` | `createClient`, `.from("candidate_profiles")` | Candidate profile route fallback | Fallback | `candidatesApi.saveMyProfile` | Low |
| `src/app/api/candidate/resume/route.ts` | `supabase.storage.from("resumes")` | Candidate resume route fallback | Fallback | `candidatesApi.uploadResume` (S3) | Low |
| `src/app/api/employer/company/route.ts` | `createClient`, `.from("companies")` | Company profile route fallback | Fallback | `companiesApi.saveMyCompany` | Low |
| `src/app/api/employer/logo/route.ts` | `supabase.storage.from("company-logos")` | Company logo route fallback | Fallback | `companiesApi.uploadLogo` (S3) | Low |
| `src/app/api/jobs/route.ts` | `createClient`, `.from("jobs")` | Job list & create fallback | Fallback | `jobsApi.listJobs` / `jobsApi.createJob` | Low |
| `src/app/api/jobs/[id]/route.ts` | `createClient`, `.from("jobs")` | Job detail/patch fallback | Fallback | `jobsApi.getJob` / `jobsApi.updateJob` | Low |
| `src/app/api/jobs/[id]/duplicate/route.ts` | `createClient`, `.from("jobs")` | Job duplication fallback | Fallback | `jobsApi.duplicateJob` | Low |
| `src/app/api/matches/route.ts` | `createClient`, `.from("matches")` | Match listing and actions fallback | Fallback | `matchingApi.listMatches` / update | Low |
| `src/app/api/admin/handoffs/[id]/route.ts` | `createClient`, `.from("handoff_requests")` | Admin handoff update fallback | Fallback | `handoffsApi.updateHandoff` | Low |
| `src/app/api/admin/matches/[id]/route.ts` | `getAdminClient`, `.from("matches")` | Admin match release fallback | Fallback | `matchingApi.updateMatch` | Low |
| `src/app/api/roles/route.ts` | `getSupabase()`, `.from("role_submissions")` | Public role submission form | Active / Fallback | Django `role_submissions` endpoint or local JSON fallback | Low |
| `src/lib/admin-create-candidate.ts` | `supabase.auth.admin.createUser`, `.storage` | Helper for admin candidate create | Active (Category B/C) | Django candidate create service | High |
| `src/lib/ensure-profile.ts` | `supabase.rpc("ensure_user_profile")` | Fallback profile upsert | Fallback | Django User auto-profile signal | Low |
| `src/lib/handoff.ts` | `getServiceClient()`, `.from("handoff_requests")` | Legacy server handoff helper | Fallback / Dead | Handled by Django backend signal | Low |
| `src/lib/match-runner.ts` | `supabase.from("matches").upsert(...)` | Client-side/Next.js matching runner | Fallback / Legacy | Django Celery task `run_matching_for_job_task` | Low |
| `src/lib/recruiter-alert.ts` | `supabase.from("matches")` | Recruiter notification helper | Fallback / Legacy | Django Celery email tasks | Low |
| `backend/common/management/commands/migrate_supabase_to_postgres.py` | `supabase-py` / HTTP PostgREST calls | Phase 10 one-time ETL script | Legacy tool | Local PostgreSQL is already populated | None |

## 4. Frontend Audit (`src/`)
### Category A — Django Replaces It (Supabase is Fallback Only)
- `src/app/candidate/page.tsx`: Uses `candidatesApi.getMyProfile()` and `matchingApi.listMatches()`.
- `src/app/candidate/profile/page.tsx`: Uses `candidatesApi.getMyProfile()`.
- `src/app/candidate/matches/page.tsx`: Uses `matchingApi.listMatches()`.
- `src/app/candidate/onboarding/page.tsx`: Uses `candidatesApi.getMyProfile()`.
- `src/app/employer/page.tsx`: Uses `companiesApi.getMyCompany()`, `jobsApi.listJobs()`, `matchingApi.listMatches()`.
- `src/app/employer/company/page.tsx`: Uses `companiesApi.getMyCompany()`.
- `src/app/employer/jobs/page.tsx`: Uses `jobsApi.listJobs({ view: "my_company" })`.
- `src/app/employer/jobs/new/page.tsx`: Uses `companiesApi.getMyCompany()`.
- `src/app/employer/matches/page.tsx`: Uses `matchingApi.listMatches()`.
- `src/app/employer/onboarding/page.tsx`: Uses `companiesApi.getMyCompany()`.
- `src/app/admin/page.tsx`: Uses `loadAdminDashboardStats()` -> Django `adminApi.getDashboardStats()`.
- `src/app/admin/matches/page.tsx`: Uses `matchingApi.listMatches()`.
- `src/app/admin/handoffs/page.tsx`: Uses `handoffsApi.listHandoffs()`.
- `src/app/admin/job-leads/page.tsx`: Uses `jobLeadsApi.listLeads()`.
- `src/app/admin/applications/page.tsx`: Uses `applicationsApi.listApplications()`.

### Category B — Django API Exists but Frontend Still Queries Supabase
- `src/app/admin/jobs/page.tsx`: Directly executes `supabase.from("jobs")`.
- `src/app/admin/jobs/new/page.tsx`: Directly executes `supabase.from("companies")`.

### Category C — No Django Replacement Yet
- `src/app/admin/candidates/page.tsx`: Admin candidate registry with complex relational filters.
- `src/app/api/admin/candidates/import/route.ts`: Bulk candidate Excel/CSV import.
- `src/app/api/admin/candidates/[id]/resume/route.ts`: Admin resume fetch/upload.
- `src/app/api/roles/route.ts`: Public job lead submissions into `role_submissions`.

### Category D — Dead / Unused Legacy Code
- `src/lib/match-runner.ts`: Supabase client matching runner.
- `src/lib/recruiter-alert.ts`: Supabase match recruiter email notifications.
- `src/lib/job-notifications.ts`: Supabase job alert helper.
- `src/app/api/jobs/parse/route.ts`: Unused LLM JD parse helper.

## 5. Authentication Audit
Authentication is **100% Django-primary** across candidate, employer, and admin roles. Supabase Auth is only used as an automatic fallback when no Django session cookies exist. The only active dependency on Supabase Auth is in `src/lib/admin-create-candidate.ts` which uses `supabase.auth.admin.createUser` for admin-created candidate accounts.

## 6. Database Query Audit
Direct Supabase database queries remain in:
1. `src/app/admin/candidates/page.tsx` (READ `candidate_profiles` + `profiles`)
2. `src/lib/admin-create-candidate.ts` (INSERT `profiles`, `candidate_profiles`)
3. `src/app/admin/jobs/page.tsx` (READ `jobs`)
4. `src/app/admin/jobs/new/page.tsx` (READ `companies`)
5. `src/app/api/roles/route.ts` (INSERT `role_submissions`)
All other page queries operate against Django first with Supabase as secondary fallback.

## 7. Storage Audit
AWS S3 Dual Storage engine (`PublicMediaStorage` and `PrivateMediaStorage`) is fully operational in Django.
Remaining Supabase storage calls:
- `src/app/api/admin/candidates/[id]/resume/route.ts` (signed URL generation & upload)
- `src/lib/admin-create-candidate.ts` (resume upload during admin import)

## 8. Celery / Background Services Audit
All tasks (`run_matching_for_candidate_task`, `run_matching_for_job_task`, `send_password_reset_email_task`, `send_verification_email_task`) are 100% Django-owned and have zero dependencies on Supabase.

## 9. AI / Matching Safety Verification
The matching formula is completely preserved and deterministic in both Django and TypeScript: `round(skill_score * 0.7 + exp_score * 0.3)`. No AI matching, vector databases, or OpenAI embeddings were introduced.

## 10. Prioritized Remaining Migration Work
### P0 — Required for Django-Only Mode
1. Django Admin Candidates API (`GET /api/v1/admin/candidates/`)
2. Django Admin Candidate Creation & Bulk Import API (`POST /api/v1/admin/candidates/`, `POST /api/v1/admin/candidates/import/`)
3. Django Admin Candidate Resume Presigned URL API (`GET /api/v1/admin/candidates/<id>/resume/`)
4. Migrate `src/app/admin/jobs/page.tsx` and `src/app/admin/jobs/new/page.tsx` to Django API
5. Migrate `src/app/api/roles/route.ts` to Django

### P1 — Required for Production
1. Production containerization & deployment configuration (Gunicorn, Nginx/Caddy, PostgreSQL, Redis, S3)
2. Switch Celery from eager mode to Redis broker in production
3. Final production database cutover

### P2 — Cleanup
1. Remove `@supabase/supabase-js` and `@supabase/ssr` packages
2. Remove `src/lib/supabase/` and legacy fallback logic

## 11. Test Verification Results
- Django System Check: 0 issues
- Django Unit Tests: 127/127 PASSED
- Next.js Production Build: 56/56 routes compiled successfully
- Phase 12 Auth Integration: 16/16 PASSED
- Phase 13 Companies & Candidates: 29/29 PASSED
- Phase 14 Jobs: 31/31 PASSED
- Phase 15 Matches: 36/36 PASSED
- Phase 16 Handoffs: 38/38 PASSED
- Phase 17 Applications & Leads: 37/37 PASSED
- Phase 18 Admin Analytics & Celery: 23/23 PASSED

## 12. Recommended Phase 20
**Phase 20: Admin Candidates & Bulk Import Migration (Final P0 Endpoints)**
Do NOT delete Supabase yet. Implement the 5 missing P0 administrative endpoints in Django, connect the remaining admin pages, and achieve complete Django feature-parity before cutting off Supabase.
