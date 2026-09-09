# Phase 18 — Pre-Migration Audit: Admin Dashboard Analytics & Background Services / Celery

**Date:** 2026-09-09  
**Status:** Completed  
**Objective:** Audit all Supabase queries used by admin dashboard analytics and navigation counters, assess existing Django APIs, and audit Celery/Redis background task architecture.

---

## 1. Admin Dashboard Analytics Audit

### Frontend Inspection (`src/lib/admin-dashboard.ts` & `src/app/admin/page.tsx`)
The admin dashboard queries a variety of metrics and preview cards. Currently:
1. `loadAdminNavCounts`:
   - `pendingMatches`: Filters matches with `visible_to_employer=false`, `match_score >= 85`, `status != 'rejected'`. Migrated in Phase 15 to `matchingApi.listMatches`, with Supabase fallback.
   - `pendingHandoffs`: Filters `handoff_requests` with `status='pending'`. Migrated in Phase 16 to `handoffsApi.listHandoffs`, with Supabase fallback.
2. `loadAdminDashboardStats`:
   Currently executes **9 parallel Supabase queries**:
   - `profiles` (new candidates created this week): `supabase.from("profiles").select("*", { count: "exact" }).eq("role", "candidate").gte("created_at", weekStart)`
   - `profiles` (new employers created this week): `supabase.from("profiles").select("*", { count: "exact" }).eq("role", "employer").gte("created_at", weekStart)`
   - `matches` (pending match previews): Top 5 matches with `visible_to_employer=false`, score >= 85
   - `matches` (candidate interested count): `supabase.from("matches").select("id", { count: "exact" }).eq("status", "candidate_interested")`
   - `matches` (candidate interest previews): Top 5 matches with `status="candidate_interested"`
   - `handoff_requests` (pending handoff previews): Top 5 pending handoffs
   - `jobs` (active jobs & unmatched jobs): Active jobs without matches
   - `candidate_profiles` (incomplete profiles previews): Top 5 incomplete profiles
   - `candidate_profiles` (incomplete profiles count): Total candidate profiles where `profile_complete=false`

### Feature Data Source & API Inventory

| Admin Feature / Metric | Current Data Source | Django API Exists? | Needs New API? | Supabase Fallback? |
|---|---|---|---|---|
| **Nav: Pending Matches** | `matchingApi.listMatches` | Yes (`/api/v1/matches/`) | No | Yes |
| **Nav: Pending Handoffs** | `handoffsApi.listHandoffs` | Yes (`/api/v1/handoffs/`) | No | Yes |
| **New Candidates This Week** | Supabase (`profiles.role = 'candidate'`) | Partial (auth/candidates) | Yes (consolidated in dashboard stats) | Retained |
| **New Employers This Week** | Supabase (`profiles.role = 'employer'`) | Partial (companies) | Yes (consolidated in dashboard stats) | Retained |
| **Candidate Interested Count**| Supabase (`matches.status = 'candidate_interested'`) | Can filter `/api/v1/matches/` | Yes (consolidated in dashboard stats) | Retained |
| **Incomplete Profiles Count** | Supabase (`candidate_profiles.profile_complete = false`) | None | Yes (consolidated in dashboard stats) | Retained |
| **Active Jobs Without Matches**| Supabase (`jobs.matches = []`) | None | Yes (consolidated in dashboard stats) | Retained |
| **Pending Match Previews** | Supabase query | Can filter `/api/v1/matches/` | Yes (consolidated in dashboard stats) | Retained |
| **Candidate Interest Previews**| Supabase query | Can filter `/api/v1/matches/` | Yes (consolidated in dashboard stats) | Retained |
| **Pending Handoff Previews** | Supabase query | Can filter `/api/v1/handoffs/` | Yes (consolidated in dashboard stats) | Retained |
| **Unmatched Job Previews** | Supabase query | None | Yes (consolidated in dashboard stats) | Retained |
| **Incomplete Profile Previews**| Supabase query | None | Yes (consolidated in dashboard stats) | Retained |

**Recommendation**: Provide a single high-performance, aggregated admin endpoint:
`GET /api/v1/admin/dashboard/stats/`
This replaces 9 fragmented Supabase round-trips with a single atomic database query using Django ORM aggregations (`Count`, `Q`, `Subquery`/`Exists`), with full Supabase fallback preserved in Next.js.

---

## 2. Celery & Background Task Audit

### Current Configuration
- Celery app defined in `backend/config/celery.py`.
- Broker & Result backend configured via `CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")`.
- `CELERY_TASK_ALWAYS_EAGER`: In development/testing when a live Redis broker is not running, tasks can be executed eagerly/synchronously without failing workflows or requiring a standing daemon.

### Background Tasks Inventory

| Task Name | Module | Purpose | Trigger | Queue | Dependencies | Current Status |
|---|---|---|---|---|---|---|
| `matching.tasks.run_matching_for_candidate_task` | `matching/tasks.py` | Asynchronous matching run when candidate completes profile | Candidate onboarding/profile save | `celery` (default) | `CandidateProfile`, `Job`, `Match` | Implemented; max_retries=3, error logging |
| `matching.tasks.run_matching_for_job_task` | `matching/tasks.py` | Asynchronous matching run when employer publishes new job | Job publish | `celery` (default) | `Job`, `CandidateProfile`, `Match` | Implemented; max_retries=3, error logging |
| `accounts.tasks.send_password_reset_email_task` | `accounts/tasks.py` | Transactional email dispatch for password reset/claim | Password reset request | `celery` (default) | `User`, `send_mail` | Currently synchronous helper in `accounts/services.py`; will expose Celery `@shared_task` with eager fallback |
| `accounts.tasks.send_verification_email_task` | `accounts/tasks.py` | Transactional email dispatch for user email verification | Registration / resend verify | `celery` (default) | `User`, `send_mail` | Currently synchronous helper in `accounts/services.py`; will expose Celery `@shared_task` with eager fallback |

### Redis Connection Verification
- Verified connection to `redis://localhost:6379/0`: Connection refused (target machine actively refused it — Redis service is not installed/running locally as a Windows service).
- **Graceful Behavior**: When Redis is not running locally, application workflows (registration, password reset, match creation, handoffs) continue to function seamlessly via synchronous fallbacks (`CELERY_TASK_ALWAYS_EAGER` or direct service calls), ensuring zero breakage or dropped errors.
