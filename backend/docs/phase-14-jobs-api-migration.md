# Phase 14 — Migrate Jobs from Supabase to Django REST Framework

## Executive Summary

Phase 14 successfully migrated the Next.js frontend's **Job management and retrieval operations** from direct Supabase database calls to the Django REST Framework backend backed by the local PostgreSQL database (`peopleremotely_local`).

The migration accomplishes the following:
1. **Preserved Frontend Structure**: Next.js App Router, layout, UI styling, forms, and workflows remain untouched.
2. **Authoritative Backend Security**: Ownership validation, company authorization, and role-based permissions (Candidate read-only, Employer own-company only, Admin full access) are strictly enforced in Django.
3. **Dual Compatibility Fallback**: Next.js Server Components and Route Handlers first query Django DRF via JWT Bearer authentication and seamlessly fall back to Supabase if compatibility mode requires it.
4. **Zero Production Risk**: Local PostgreSQL migration only; Supabase production data and authentication remain completely unaltered.

---

## 1. Existing Job Architecture vs. Migrated Architecture

### Before Phase 14 (Supabase Data Layer for Jobs)

```text
Next.js Frontend (Server & Client Components)
   │
   ├── supabase.from('jobs').select(...)
   ├── supabase.from('jobs').insert(...)
   ├── supabase.from('jobs').update(...)
   └── supabase.from('companies').select('id').eq('owner_id', ...)
```

### After Phase 14 (Django REST Framework Primary + Supabase Fallback)

```text
Next.js Frontend (Server & Client Components)
   │
   ├── HttpOnly Cookie / Authorization: Bearer <access_token>
   ▼
Django REST Framework API (`/api/v1/jobs/`)
   ├── GET    /api/v1/jobs/?view=my_company   (Employer company roles)
   ├── GET    /api/v1/jobs/                   (Public / Candidate active jobs)
   ├── POST   /api/v1/jobs/                   (Employer create job)
   ├── GET    /api/v1/jobs/<id>/              (Job detail - owner vs public)
   ├── PATCH  /api/v1/jobs/<id>/              (Update status / fields)
   ├── POST   /api/v1/jobs/<id>/duplicate/    (Duplicate job as draft)
   └── DELETE /api/v1/jobs/<id>/              (Delete job)
   ▼
Local PostgreSQL (`peopleremotely_local`)
```

---

## 2. Django Job Model & Serialization

The Django `Job` model in `backend/jobs/models.py` maps 1:1 with the Supabase schema:
* `id` (UUIDField, primary key)
* `company` (ForeignKey to `Company`, related_name `jobs`)
* `posted_by` (ForeignKey to `User`, related_name `posted_jobs`)
* `title` (CharField)
* `description` (TextField)
* `role_type` (`contract`, `c2h`, `full-time`)
* `experience_level` (`junior`, `mid`, `senior`, `lead`)
* `tech_stack` (JSONField: array of skills)
* `salary_range` (CharField: validated against deceptive terms like "Competitive" or "DOE")
* `work_type` (CharField: `remote`, `hybrid`, `onsite`)
* `visa_requirements` (TextField: work authorization eligibility description)
* `status` (`draft`, `active`, `paused`, `closed`, `archived`)
* `expires_at` (DateTimeField: 30-day expiry set upon activation)
* `jd_quality_score`, `jd_quality_feedback`, `featured`
* `created_at`, `updated_at`

### Serializer Refinements
In `backend/jobs/serializers.py`:
* `JobSerializer`: Added `company_id` and `companies` fields to match the Next.js `Job` TypeScript interface (`src/lib/types.ts`), providing full compatibility.
* `JobCreateUpdateSerializer`: Configured `tech_stack = serializers.JSONField(required=False)` to seamlessly support both JSON arrays and comma-separated string inputs from forms and AI parser tools.

---

## 3. Endpoints & Permission Matrix

| Endpoint | Method | Allowed Roles | Description |
|---|---|---|---|
| `/api/v1/jobs/?view=my_company` | `GET` | Employer, Admin | Returns jobs belonging only to authenticated user's company |
| `/api/v1/jobs/` | `GET` | Anyone, Candidate | Returns only active, non-expired public roles |
| `/api/v1/jobs/` | `POST` | Employer, Admin | Creates a job for owned company. Candidate gets `403 Forbidden` |
| `/api/v1/jobs/<pk>/` | `GET` | Anyone | Full view for owner/admin, sanitized view for public/candidates |
| `/api/v1/jobs/<pk>/` | `PATCH` | Owner, Admin | Updates status (`active`, `paused`, `closed`, `archived`). Competitor gets `403` |
| `/api/v1/jobs/<pk>/duplicate/` | `POST` | Owner, Admin | Creates a cloned draft copy with `(copy)` title |
| `/api/v1/jobs/<pk>/` | `DELETE` | Owner, Admin | Deletes job. Competitor gets `403` |

---

## 4. Frontend Integration Points Modified

### 1. API Client (`src/lib/api/jobs.ts`)
* Added `getMyJobs(options)`: Calls `/api/v1/jobs/?view=my_company`.
* Added `company_id` and `companies` fields to `DjangoJob` interface.
* Enhanced `createJob`, `updateJob`, `duplicateJob`, `deleteJob`, `listJobs`, and `getJob` with Bearer token forwarding.

### 2. Server Pages Migrated
* **`src/app/employer/jobs/page.tsx`**:
  * Resolves company via `companiesApi.getMyCompany({ token })` (fallback to Supabase).
  * Loads company roles via `jobsApi.getMyJobs({ token })` (fallback to Supabase).
* **`src/app/employer/jobs/new/page.tsx`**:
  * Resolves company via `companiesApi.getMyCompany({ token })` (fallback to Supabase).
* **`src/app/employer/page.tsx` (Dashboard)**:
  * Resolves company jobs and role counts via `jobsApi.getMyJobs({ token })` (fallback to Supabase).
* **`src/app/employer/matches/page.tsx`**:
  * Resolves active company jobs for filter dropdowns via `jobsApi.getMyJobs({ token })` (fallback to Supabase).

### 3. Route Handlers Migrated
* **`src/app/api/jobs/route.ts` (POST)**:
  * Authenticates via `getSessionProfile()` and `getAccessToken()`.
  * Resolves employer company via Django API first.
  * Calls `jobsApi.createJob(payload, { token })`.
  * Preserves Supabase database fallback.
* **`src/app/api/jobs/[id]/route.ts` (PATCH)**:
  * Authenticates via `getSessionProfile()` and `getAccessToken()`.
  * Calls `jobsApi.updateJob(id, { status }, { token })`.
  * Preserves Supabase database fallback.
* **`src/app/api/jobs/[id]/duplicate/route.ts` (POST)**:
  * Authenticates via `getSessionProfile()` and `getAccessToken()`.
  * Calls `jobsApi.duplicateJob(id, { token })`.
  * Preserves Supabase database fallback.

---

## 5. Verification & Test Results

### 1. Automated Phase 14 Jobs Integration Tests (`scripts/test-phase14-jobs.mjs`)
* **Total checks**: 31/31 PASSED (100%).
* **Key flows verified**:
  * Employer 1 & 2 registration + company creation: PASS
  * Candidate registration: PASS
  * Job creation with 30-day expiry: PASS
  * Employer job listing with `view=my_company` (Employer 1 sees 1, Employer 2 sees 0): PASS
  * Owner vs. public job detail inspection: PASS
  * Job status transition (active -> paused -> active): PASS
  * Job duplication as draft with `(copy)` suffix: PASS
  * Candidate write rejection (HTTP 403): PASS
  * Candidate patch rejection (HTTP 403): PASS
  * Cross-employer modification rejection / IDOR prevention (HTTP 403): PASS
  * Cross-employer duplication rejection (HTTP 403): PASS

### 2. Regression Testing: Phase 12 & 13 Integration Tests
* **Phase 12 Auth Integration Tests** (`test-phase12-auth.mjs`): **16/16 PASSED**.
* **Phase 13 Companies/Candidates Integration Tests** (`test-phase13-companies-candidates.mjs`): **29/29 PASSED**.

### 3. Backend Django Unit & API Tests (`python manage.py test`)
* **Ran**: 113 tests (added 3 new comprehensive test cases for candidate write rejection, admin lifecycle, and company isolation).
* **Result**: **113/113 PASSED (OK)**.
* **System check**: 0 issues.

### 4. Next.js Production Build (`npm run build`)
* **Compilation**: Turbopack compiled in 20.8s.
* **TypeScript check**: 0 errors.
* **Route Generation**: All 56/56 routes compiled successfully.

---

## 6. Supabase Inventory Classification

| Domain | Table / Query | Status | Note |
|---|---|---|---|
| Jobs | `jobs` table list, create, update, duplicate | **MIGRATED** | Primary handler is Django DRF `/api/v1/jobs/`. Supabase retained as compatibility fallback. |
| Companies | `companies`, `company_members`, logos | **MIGRATED** | Completed in Phase 13. |
| Candidates | `candidate_profiles`, resumes | **MIGRATED** | Completed in Phase 13. |
| Auth | JWT Auth, login, logout, refresh, reset | **MIGRATED** | Completed in Phase 12. |
| Matches | `matches` table operations | **NOT YET MIGRATED** | Intentionally scheduled for Phase 15. |
| Handoffs | `handoffs` table operations | **NOT YET MIGRATED** | Intentionally scheduled for Phase 16. |
| Admin | Admin moderation operations | **NOT YET MIGRATED** | Intentionally scheduled for Phase 17. |

---

## 7. Production Safety Checklist

* [x] Supabase production records modified: **NO**
* [x] Supabase production schema modified: **NO**
* [x] Supabase production Auth modified: **NO**
* [x] Production deployment performed: **NO**
* [x] Production data modified: **NO**
* [x] Ready for Phase 15: **YES**
