# Phase 18 — Admin Dashboard Analytics & Background Services / Celery Verification Report

## 1. Overview & Architecture

Phase 18 accomplishes two objectives:
1. **Admin Dashboard Analytics Migration**: Replaces 9 separate Supabase round-trip queries executed on every admin dashboard visit with a single, high-performance aggregated Django REST Framework endpoint `GET /api/v1/admin/dashboard/stats/` powered by atomic PostgreSQL ORM aggregations (`Count`, `Q`, `select_related`).
2. **Background Services & Celery Verification**: Formalizes Celery background tasks across `matching` and `accounts`, verifies task autodiscovery and error resilience, and confirms local execution safety preventing accidental production email dispatches or real side-effects.

```
Next.js Frontend (/admin dashboard)
        │
        ├── queries adminApi.getDashboardStats()
        ▼
Django REST API (/api/v1/admin/dashboard/stats/)
        │  (Strict IsAdmin permission, atomic ORM aggregations)
        ▼
Local PostgreSQL (peopleremotely_local)
        ▲
        │
Celery Task Queue & Workers
        ├── matching.tasks.run_matching_for_candidate_task
        ├── matching.tasks.run_matching_for_job_task
        ├── accounts.tasks.send_password_reset_email_task
        └── accounts.tasks.send_verification_email_task
```

---

## 2. Initial Audit Findings

### Admin Dashboard Analytics Queries
Before Phase 18, [src/lib/admin-dashboard.ts](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/lib/admin-dashboard.ts) executed 9 parallel Supabase queries:
1. `profiles`: new candidates created this week (`role='candidate'`, `created_at >= weekStart`).
2. `profiles`: new employers created this week (`role='employer'`, `created_at >= weekStart`).
3. `matches`: pending match previews (top 5 with `visible_to_employer=false`, `match_score >= 85`).
4. `matches`: candidate interested count (`status='candidate_interested'`).
5. `matches`: candidate interest previews (top 5 with `status='candidate_interested'`).
6. `handoff_requests`: pending handoff previews (top 5 with `status='pending'`).
7. `jobs`: active jobs with 0 matches (`status='active'`, `matches=[]`).
8. `candidate_profiles`: incomplete profiles previews (top 5 with `profile_complete=false`).
9. `candidate_profiles`: incomplete profiles count.

### Background Services & Celery Configuration
- **Celery Application**: Configured in `backend/config/celery.py`.
- **Redis Connection**: Verified `redis://localhost:6379/0`. The local machine actively refused the connection, indicating Redis is not running as a local Windows service.
- **Fail-Safe Eager Mode**: Configured `CELERY_TASK_ALWAYS_EAGER = True` and `CELERY_TASK_EAGER_PROPAGATES = True` in development, allowing tasks to execute synchronously and reliably without failing workflows or dropping exceptions.

---

## 3. Backend Implementation

### A. Admin Dashboard Analytics View (`backend/common/dashboard_views.py`)
- Mounted at `GET /api/v1/admin/dashboard/stats/`.
- Strict `IsAdmin` permission (`IsAuthenticated` + `role == 'admin'`). Candidates, Employers, and unauthenticated users are rejected with `HTTP 403 Forbidden` / `HTTP 401 Unauthorized`.
- Queries:
  - `newCandidatesThisWeek`: `User.objects.filter(role=User.Role.CANDIDATE, created_at__gte=week_start).count()`
  - `newEmployersThisWeek`: `User.objects.filter(role=User.Role.EMPLOYER, created_at__gte=week_start).count()`
  - `pendingMatches`: `Match.objects.filter(visible_to_employer=False, match_score__gte=85).exclude(status=Match.Status.REJECTED).count()`
  - `pendingHandoffs`: `HandoffRequest.objects.filter(status=HandoffRequest.Status.PENDING).count()`
  - `activeJobsWithNoMatches`: `Job.objects.annotate(match_count=Count("matches")).filter(status=Job.Status.ACTIVE, match_count=0).count()`
  - Previews for pending matches, candidate interest, pending handoffs, unmatched jobs, and incomplete profiles formatted with exact TypeScript interface compatibility.

### B. Background Tasks (`matching/tasks.py` and `accounts/tasks.py`)
- **Matching Tasks**:
  - `matching.tasks.run_matching_for_candidate_task(candidate_profile_id)`
  - `matching.tasks.run_matching_for_job_task(job_id)`
  - Uses exact deterministic matching formula: `round(skill_score * 0.7 + exp_score * 0.3)`.
- **Email Tasks**:
  - `accounts.tasks.send_password_reset_email_task(to_email, uidb64, token)`
  - `accounts.tasks.send_verification_email_task(to_email, uidb64, token)`
  - Uses Django test email backend in local development; suppresses external network calls and avoids sending real emails to production users.
- **Task Discovery**: AppConfig `ready()` methods in `matching/apps.py` and `accounts/apps.py` ensure all tasks are registered cleanly in Celery's task registry.

---

## 4. Frontend Integration

- **Admin API Client** (`src/lib/api/admin.ts`):
  - Created `adminApi.getDashboardStats(options)` returning typed `DjangoAdminDashboardStats`.
  - Re-exported from `src/lib/api/index.ts`.
- **Dashboard Loader** (`src/lib/admin-dashboard.ts`):
  - Updated `loadAdminDashboardStats()` to query `adminApi.getDashboardStats()` first.
  - Automatically falls back to Supabase if Django is unreachable.

---

## 5. Test Verification & Results

### Phase 18 Dedicated Test Suite (`scripts/test-phase18-admin-celery.mjs`)
- **23/23 PASSED (100%)**
  - Admin login & JWT token retrieval
  - Candidate and employer registration & token retrieval
  - Admin queries `GET /api/v1/admin/dashboard/stats/` $\to$ HTTP 200 with all numeric metrics and preview arrays
  - Candidate denied dashboard stats $\to$ HTTP 403 Forbidden (RBAC verification)
  - Employer denied dashboard stats $\to$ HTTP 403 Forbidden (RBAC verification)
  - Unauthenticated access denied $\to$ HTTP 401 Unauthorized
  - Celery task discovery verified: `run_matching_for_candidate_task`, `run_matching_for_job_task`, `send_password_reset_email_task`, `send_verification_email_task` registered
  - Celery email task execution tested safely without production side-effects

### Regression Test Suite
- **Django Unit Tests (`python manage.py test`)**: **110/110 PASSED** (6 new Phase 18 unit tests)
- **Django System Check (`python manage.py check`)**: **0 issues identified**
- **Phase 12 Auth Integration**: 16/16 PASSED
- **Phase 13 Companies & Candidates Integration**: 29/29 PASSED
- **Phase 14 Jobs Integration**: 31/31 PASSED
- **Phase 15 Matches Integration**: 36/36 PASSED
- **Phase 16 Handoffs Integration**: 38/38 PASSED
- **Phase 17 Applications & Job Leads Integration**: 37/37 PASSED
- **Next.js Production Build (`npm run build`)**: **56/56 routes compiled successfully**

---

## 6. Production Safety Audit

| Requirement | Result |
|---|---|
| Supabase production records modified | **NO** |
| Supabase Auth modified | **NO** |
| Supabase Storage modified | **NO** |
| Production deployment performed | **NO** |
| Production emails sent | **NO** |
| External Redis broker modified | **NO** (Safe local test mode / eager execution) |
| AI matching redesigned | **NO** (Deterministic algorithm `round(skill_score * 0.7 + exp_score * 0.3)` preserved) |
| Supabase fallback active | **YES** |
| Next.js build passed | **YES (56/56 routes)** |
