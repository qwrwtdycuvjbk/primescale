# Phase 17 — Pre-Migration Audit: Job Applications & Job Leads

**Date:** 2026-09-09  
**Status:** Completed  
**Objective:** Audit existing Supabase schema, Next.js frontend pages/components, and Django backend models to determine the real state of Job Applications and Job Leads before modifying code.

---

## 1. Executive Summary & Core Findings

1. **Job Applications Table Does NOT Exist in Supabase**:
   - As audited in Phase 9 and documented in [backend/ARCHITECTURE.md](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/backend/ARCHITECTURE.md), there is **no `applications` table** in the Supabase PostgreSQL database.
   - Candidate job interest and applications are modeled using `matches`:
     - Initial state: `status = 'suggested'`
     - Candidate applies/expresses interest: `status = 'candidate_interested'`
     - Employer reviews/shortlists: `status = 'employer_shortlisted'`
     - Mutual match reached: `status = 'mutual_fit'` $\to$ provisions `handoff_requests`
   - In Next.js:
     - The page [src/app/admin/applications/page.tsx](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/app/admin/applications/page.tsx) is literally an HTTP redirect to `/admin/candidates`.
     - In marketing copy, People Remotely explicitly states: *"Build your profile once. We match you to remote tech roles we’re actively filling — not a spam apply button."*
   - **However**, for strict REST compatibility and Phase 17 compliance, we will provide a dedicated Django REST API endpoint `/api/v1/applications/` and Next.js client `src/lib/api/applications.ts` that provides an applications view over the candidate application workflow (allowing candidates to apply to jobs, list their applications, and employers/admins to review applications and update status).

2. **Job Leads Architecture & External Source Status**:
   - Job leads are displayed in Next.js at `/admin/job-leads` via [src/app/admin/job-leads/page.tsx](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/app/admin/job-leads/page.tsx).
   - They are queried through the API route [src/app/api/admin/job-leads/route.ts](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/app/api/admin/job-leads/route.ts), which calls [src/lib/openweb-ninja.ts](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/lib/openweb-ninja.ts).
   - **Data Storage**: Job leads are **ephemeral, search-driven remote tech leads** fetched on-demand from the OpenWeb Ninja JSearch API (`https://api.openwebninja.com/jsearch`) using the environment variable `OPENWEB_NINJA_API_KEY`.
   - **Database Tables**: There is **no `job_leads` table** in Supabase, nor is there any scheduled Celery/cron database ingestion running.
   - **External Provider Constraint**: In compliance with the Phase 17 prompt:
     > *"The user currently does NOT have an external job-leads data provider/API... If the existing system contains job leads, first inspect how they currently work. If there is no real external source, create only the backend/API structure required by the existing functionality and make it extensible for a future provider. Do NOT fabricate external job data."*
   - OpenWeb Ninja JSearch is already integrated into the Next.js admin app as a live search tool. We will create a clean Django backend module `backend/job_leads/` (with endpoints `/api/v1/job-leads/`) that provides the backend/API foundation for job leads, extensible for any future provider or internal saved leads, and wire the Next.js client `src/lib/api/job-leads.ts` accordingly.

---

## 2. Migration Inventory

| Item | Supabase / Frontend State | Django Backend State | Migration Plan |
|---|---|---|---|
| **Applications Table** | Not a table; represented by `matches` with `candidate_interested`, `mutual_fit` | No standalone `applications` table; `matching.Match` handles candidate applications | Implement `/api/v1/applications/` viewset / endpoints backed by `Match` (or clean application adapter) ensuring candidate apply, candidate list, employer review, and status transitions work seamlessly |
| **Candidate Apply** | Clicking "I'm interested" on a match PATCHes `/api/matches` status to `candidate_interested` | Supported via `/api/v1/matches/<id>/` PATCH status and new `/api/v1/applications/apply/` | Provide explicit `POST /api/v1/applications/apply/` and `GET /api/v1/applications/` |
| **Duplicate Applications** | Unique constraint on `(candidate_profile, job)` in `matches` table | Enforced by `models.UniqueConstraint(fields=["candidate_profile", "job"])` | Prevent duplicate application submissions with 400 Bad Request |
| **Employer Application Review** | Employers review candidates on `/employer/matches` | Supported via `/api/v1/matches/` | Support `/api/v1/applications/` with employer job scoping |
| **Admin Applications** | `/admin/applications` redirects to `/admin/candidates` | N/A | Admin can list all applications via `/api/v1/applications/` |
| **Job Leads Storage** | Ephemeral search queries to OpenWeb Ninja JSearch API | None | Implement `backend/job_leads/` app with `/api/v1/job-leads/` supporting search, saved leads, and extensible provider interface |
| **Job Leads Admin UI** | `/admin/job-leads` with preset filters and worldwide/country scopes | N/A | Provide `src/lib/api/job-leads.ts` with Django proxy fallback to current route handler |

---

## 3. Detailed Status Workflow & Permissions

### Status Lifecycle for Applications
1. `suggested`: System recommends job to candidate (or candidate discovers active job).
2. `candidate_interested` (Applied): Candidate submits application (`POST /api/v1/applications/apply/` or expresses interest).
3. `employer_shortlisted`: Employer reviews application and shortlists candidate.
4. `mutual_fit`: Both parties are aligned $\to$ automatic `HandoffRequest` provisioned.
5. `rejected`: Either candidate or employer passes on the application.

### Strict Permissions & IDOR Matrix
- **Candidate**:
  - `GET /api/v1/applications/`: Returns only applications for `request.user.candidate_profile`.
  - `GET /api/v1/applications/<id>/`: Returns 403 Forbidden if not the candidate owner.
  - `POST /api/v1/applications/apply/`: Can only apply with own candidate profile. Cannot apply to inactive/closed jobs. Rejects duplicates with 400.
  - Cannot modify employer review fields or recruiter notes.
- **Employer**:
  - `GET /api/v1/applications/`: Returns only applications for jobs posted by `request.user` or belonging to `request.user.company`.
  - `GET /api/v1/applications/<id>/`: Returns 403 Forbidden if job does not belong to employer.
  - `PATCH /api/v1/applications/<id>/`: Can only transition status to `employer_shortlisted` or `rejected`. Cannot modify candidate details.
- **Admin**:
  - Global read and status update permissions.
