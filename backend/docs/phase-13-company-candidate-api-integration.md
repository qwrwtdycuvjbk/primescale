# Phase 13 — Companies + Candidate Profiles API Integration

## Executive Summary

Phase 13 successfully migrated the Next.js frontend's **Company** and **Candidate Profile** operations from direct Supabase database and storage calls to Django REST Framework (DRF) APIs backed by the local PostgreSQL database (`peopleremotely_local`).

The migration preserves:
1. Complete Next.js architecture (App Router, Server Components, client forms) without any redesign or framework alterations.
2. Full Supabase compatibility fallback for progressive transition.
3. Strict isolation: Jobs, Matches, Handoffs, and Admin workflows remain untouched for upcoming phases.
4. Security: Authoritative role-based access control enforced directly by Django.
5. Storage: Candidate resumes and company logos are handled through Django's S3/local storage foundation with presigned URL security for private resumes.

---

## 1. Before vs. After Architecture

### Before Phase 13 (Supabase Data Layer for Companies & Candidates)

```text
Next.js Frontend (Server & Client Components)
   │
   ├── supabase.from('companies').select / insert / update
   ├── supabase.from('candidate_profiles').select / insert / update
   ├── supabase.from('company_members').select / insert
   └── supabase.storage.from('resumes' / 'company-logos').upload
```

### After Phase 13 (Django REST Framework Primary + Supabase Fallback)

```text
Next.js Frontend (Server & Client Components)
   │
   ├── HttpOnly Cookie / Authorization: Bearer <token>
   ▼
Django REST Framework API (`/api/v1/`)
   ├── /api/v1/companies/me/          (CompanyMeView)
   ├── /api/v1/companies/<id>/        (CompanyDetailView)
   ├── /api/v1/companies/<id>/members/ (CompanyMembersView)
   ├── /api/v1/companies/me/logo/     (CompanyLogoUploadView)
   ├── /api/v1/candidates/me/         (CandidateMeView)
   ├── /api/v1/candidates/me/resume/  (CandidateResumeView)
   └── /api/v1/candidates/public-showcase/ (PublicTalentShowcaseView)
   ▼
Local PostgreSQL (`peopleremotely_local`) & S3 Storage Foundation
```

---

## 2. Django Endpoints Utilized & Tested

| Method | Endpoint | View Class | Description |
|---|---|---|---|
| `GET` | `/api/v1/companies/me/` | `CompanyMeView` | Retrieves authenticated employer's company profile |
| `POST` | `/api/v1/companies/me/` | `CompanyMeView` | Creates or updates current employer's company |
| `PATCH` | `/api/v1/companies/me/` | `CompanyMeView` | Partial update of employer's company |
| `GET` | `/api/v1/companies/<pk>/` | `CompanyDetailView` | Public or detail inspection of company |
| `GET` | `/api/v1/companies/<pk>/members/` | `CompanyMembersView` | Lists company members |
| `POST` | `/api/v1/companies/<pk>/members/` | `CompanyMembersView` | Adds recruiter/admin member to company |
| `POST` | `/api/v1/companies/me/logo/` | `CompanyLogoUploadView` | S3 public logo upload |
| `GET` | `/api/v1/candidates/me/` | `CandidateMeView` | Retrieves authenticated candidate's profile |
| `POST` | `/api/v1/candidates/me/` | `CandidateMeView` | Creates or updates candidate profile & synchronizes phone |
| `PATCH` | `/api/v1/candidates/me/` | `CandidateMeView` | Partial candidate profile update |
| `POST` | `/api/v1/candidates/me/resume/` | `CandidateResumeView` | Uploads private resume to S3 storage |
| `GET` | `/api/v1/candidates/me/resume/` | `CandidateResumeView` | Generates temporary presigned download URL |
| `GET` | `/api/v1/candidates/public-showcase/` | `PublicTalentShowcaseView` | Anonymized talent showcase cards |

---

## 3. Frontend Integration Points Modified

### Centralized API Client (`src/lib/api/`)
* **`src/lib/api/companies.ts`**:
  * `getMyCompany(options)`: Calls `GET /api/v1/companies/me/`.
  * `saveMyCompany(data, options)`: Maps form fields to snake_case and calls `POST /api/v1/companies/me/`.
  * `uploadLogo(file, options)`: Multipart upload to `/api/v1/companies/me/logo/`.
  * `getCompanyById(id, options)`: Calls `GET /api/v1/companies/${id}/`.
  * `getCompanyMembers(companyId, options)`: Calls `GET /api/v1/companies/${companyId}/members/`.
* **`src/lib/api/candidates.ts`**:
  * `getMyProfile(options)`: Calls `GET /api/v1/candidates/me/`.
  * `saveMyProfile(data, options)`: Formats skills and payload, calls `POST /api/v1/candidates/me/`.
  * `uploadResume(file, options)`: Multipart upload to `/api/v1/candidates/me/resume/`.
  * `getResumeDownloadUrl(options)`: Fetches presigned download URL from `/api/v1/candidates/me/resume/`.
  * `getPublicShowcase(limit, options)`: Calls `/api/v1/candidates/public-showcase/`.

### Authentication & Token Helper (`src/lib/auth.ts`)
* Added `getAccessToken()` helper that extracts the JWT `access_token` from Next.js server cookies (`cookies()`), enabling server-side components to pass authorization headers to the Django API.

### Server Pages Updated with Django First & Supabase Fallback
1. **`src/app/auth/redirect/page.tsx`**:
   * Inspects `profile.role`.
   * For employers, checks `companiesApi.getMyCompany({ token })` before redirecting to `/employer` or `/employer/onboarding`.
   * For candidates, checks `candidatesApi.getMyProfile({ token })` before redirecting to `/candidate` or `/candidate/onboarding`.
   * Falls back to Supabase if the Django API call fails or returns 404.
2. **`src/app/candidate/onboarding/page.tsx`**:
   * Retrieves existing profile via `candidatesApi.getMyProfile({ token })` with Supabase fallback.
3. **`src/app/candidate/profile/page.tsx`**:
   * Retrieves existing profile via `candidatesApi.getMyProfile({ token })` with Supabase fallback.
4. **`src/app/candidate/page.tsx` (Dashboard)**:
   * Fetches profile via `candidatesApi.getMyProfile({ token })` for completeness status with Supabase fallback.
5. **`src/app/employer/onboarding/page.tsx`**:
   * Retrieves existing company via `companiesApi.getMyCompany({ token })` with Supabase fallback.
6. **`src/app/employer/company/page.tsx`**:
   * Retrieves existing company via `companiesApi.getMyCompany({ token })` with Supabase fallback.
7. **`src/app/employer/page.tsx` (Dashboard)**:
   * Fetches company via `companiesApi.getMyCompany({ token })` with Supabase fallback.
8. **`src/app/employer/matches/page.tsx`**:
   * Fetches company via `companiesApi.getMyCompany({ token })` with Supabase fallback.

### API Routes Updated (`src/app/api/`)
1. **`src/app/api/employer/company/route.ts`**:
   * Authenticates using `getSessionProfile()` and forwards `getAccessToken()` to `companiesApi.saveMyCompany()`.
   * Supabase database fallback preserved.
2. **`src/app/api/employer/logo/route.ts`**:
   * Authenticates using `getSessionProfile()` and forwards token to `companiesApi.uploadLogo()`.
   * Supabase storage fallback preserved.
3. **`src/app/api/candidate/profile/route.ts`**:
   * Authenticates using `getSessionProfile()` and forwards `getAccessToken()` to `candidatesApi.saveMyProfile()`.
   * Supabase database fallback preserved.
4. **`src/app/api/candidate/resume/route.ts`**:
   * Authenticates using `getSessionProfile()` and forwards token to `candidatesApi.uploadResume()`.
   * Supabase storage fallback preserved.

---

## 4. Backend Refinements
* In `backend/candidates/serializers.py` (`CandidateProfileInputSerializer`), updated the `skills` field definition to accept both JSON array lists and comma-separated strings (`skills = serializers.JSONField(required=False)`), seamlessly supporting both frontend wizard payloads and REST API invocations.

---

## 5. Verification & Test Results

### 1. Automated Phase 13 Integration Tests (`scripts/test-phase13-companies-candidates.mjs`)
* **Total checks**: 29/29 PASSED.
* **Test flows verified**:
  * Candidate Registration via DRF: HTTP 201
  * Candidate Profile Creation via `POST /api/v1/candidates/me/`: HTTP 200/201
  * Candidate Profile Retrieval via `GET /api/v1/candidates/me/`: HTTP 200
  * Candidate Resume Upload via `POST /api/v1/candidates/me/resume/`: HTTP 200
  * Candidate Resume Presigned URL via `GET /api/v1/candidates/me/resume/`: HTTP 200
  * Employer Registration via DRF: HTTP 201
  * Company Creation via `POST /api/v1/companies/me/`: HTTP 201
  * Company Profile Retrieval via `GET /api/v1/companies/me/`: HTTP 200
  * Company Detail by ID via `GET /api/v1/companies/<id>/`: HTTP 200
  * Company Logo Upload via `POST /api/v1/companies/me/logo/`: HTTP 200
  * Company Member Access via `GET /api/v1/companies/<id>/members/`: HTTP 200
  * Authorization Boundaries: Candidate forbidden on `/companies/me/` (403)
  * Authorization Boundaries: Employer forbidden on `/candidates/me/` (403)
  * Unauthenticated rejection: 401 on protected candidate and company routes

### 2. Phase 12 Authentication Integration Tests (`scripts/test-phase12-auth.mjs`)
* **Total checks**: 16/16 PASSED.

### 3. Backend Django Tests (`python manage.py test`)
* **Ran 110 tests**: 110/110 PASSED (OK).
* System check: 0 issues.

### 4. Next.js Production Build (`npm run build`)
* **Compilation**: Compiled successfully with Turbopack in 23.3s.
* **Type Check**: 0 errors.
* **Route Generation**: 56/56 routes compiled successfully.

---

## 6. Supabase Inventory Classification

| Domain | Operation / Table | Status | Note |
|---|---|---|---|
| Companies | `GET / POST / PATCH companies` | **MIGRATED** | Primary handler is DRF `CompanyMeView` & `CompanyDetailView`. Supabase retained as compatibility fallback. |
| Companies | `company_members` | **MIGRATED** | Handled by DRF `CompanyMembersView`. |
| Companies | Logo upload (`company-logos`) | **MIGRATED** | Handled by DRF `CompanyLogoUploadView` into S3 storage. |
| Candidate Profiles | `GET / POST / PATCH candidate_profiles` | **MIGRATED** | Primary handler is DRF `CandidateMeView`. Supabase retained as compatibility fallback. |
| Candidate Profiles | Resume upload & download (`resumes`) | **MIGRATED** | Handled by DRF `CandidateResumeView` with presigned S3 URLs. |
| Jobs | `jobs` table operations | **NOT YET MIGRATED** | Intentionally scheduled for Phase 14. |
| Matches | `matches` table operations | **NOT YET MIGRATED** | Scheduled for Phase 15. |
| Handoffs | `handoffs` table operations | **NOT YET MIGRATED** | Scheduled for Phase 16. |
| Admin | Admin moderation operations | **NOT YET MIGRATED** | Scheduled for Phase 17. |
| Auth Fallback | Supabase Auth cookie / session | **INTENTIONALLY RETAINED** | Maintained for fallback compatibility until final production cutover. |

---

## 7. Final Checklist

* [x] Company API integration: **PASS**
* [x] Candidate API integration: **PASS**
* [x] Company onboarding: **PASS**
* [x] Candidate onboarding: **PASS**
* [x] Company editing: **PASS**
* [x] Candidate editing: **PASS**
* [x] Company members: **PASS**
* [x] Resume integration: **PASS**
* [x] Logo integration: **PASS**
* [x] Authentication: **PASS**
* [x] Authorization: **PASS**
* [x] Data persistence: **PASS**
* [x] UUID preservation: **PASS**
* [x] Frontend tests: **PASS (16/16 Auth + 29/29 Comp/Cand)**
* [x] Backend tests: **PASS (110/110)**
* [x] Supabase production modified: **NO**
* [x] Supabase production data modified: **NO**
* [x] Supabase production auth modified: **NO**
* [x] Production deployment: **NO**
* [x] Jobs migrated: **NO**
* [x] Matches migrated: **NO**
* [x] Handoffs migrated: **NO**
* [x] Admin APIs migrated: **NO**
* [x] Ready for Phase 14: **YES**
