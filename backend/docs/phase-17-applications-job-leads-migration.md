# Phase 17 — Job Applications & Job Leads Migration Report

## 1. Overview & Architecture

Phase 17 successfully migrates the **Job Applications** and **Job Leads** domain modules from Supabase to **Django REST Framework** backed by local PostgreSQL (`peopleremotely_local`), while maintaining non-breaking Supabase compatibility fallbacks.

```
Next.js Frontend (App Router)
   ├── Candidate / Employer / Admin Application workflows
   ├── Admin Job Leads Search & Saved Pipeline
   │
   ▼
Next.js API Client Layer
   ├── src/lib/api/applications.ts
   ├── src/lib/api/job-leads.ts
   │
   ▼
Django REST API (/api/v1/)
   ├── /api/v1/applications/ (List, Apply, Detail, Status Update)
   ├── /api/v1/job-leads/ (List, Search, Create/Save Lead)
   │
   ▼
Local PostgreSQL (`peopleremotely_local`)
```

---

## 2. Existing Supabase Implementation vs. Django Implementation

### Job Applications
- **Supabase Audit Findings**: As confirmed during the pre-migration audit, there was **no `applications` table** in the Supabase PostgreSQL database schema. In People Remotely, candidate applications and expressions of interest were modeled through `matches.status` (`suggested` $\to$ `candidate_interested` [applied] $\to$ `employer_shortlisted` $\to$ `mutual_fit` $\to$ `handoff_requests`).
- **Django REST Implementation (`backend/applications/`)**:
  - Implemented `/api/v1/applications/` and `/api/v1/applications/apply/` backed by `matching.models.Match`.
  - Reusing the relational Match graph guarantees 100% data integrity, preserves UUIDs, prevents duplicate applications to the same job at the database level (`unique_candidate_job_match`), and links directly with recruiter handoffs.
  - Exposes `ApplicationSerializer` with shape compatibility for candidate and employer views (`job`, `jobs`, `candidate_profile`, `candidate_profiles`, `applied_at`, `status`).

### Job Leads
- **Audit Findings**: The application did not have a database table for job leads; `/admin/job-leads` queries [src/lib/openweb-ninja.ts](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/lib/openweb-ninja.ts) on-demand using OpenWeb Ninja's JSearch API (`OPENWEB_NINJA_API_KEY`).
- **External Provider Status**: As instructed, no external provider was invented or fabricated.
- **Django Implementation (`backend/job_leads/`)**:
  - Created `backend/job_leads/models.py` (`JobLead`) with fields matching the Next.js `RemoteTechJobLead` interface (`external_id`, `title`, `company`, `apply_url`, `is_remote`, etc.).
  - Created `/api/v1/job-leads/` endpoints with strict Admin-only permissions (`403 Forbidden` for candidates and employers).
  - Updated [src/app/api/admin/job-leads/route.ts](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/src/app/api/admin/job-leads/route.ts) to query Django first with fallback to live search.

---

## 3. Endpoints & REST Conventions

### Applications (`/api/v1/applications/`)

| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/v1/applications/` | Candidate, Employer, Admin | Lists applications scoped to user role. Candidates see jobs they applied to. Employers see candidates who applied to their jobs. Admins see all. |
| `POST` | `/api/v1/applications/apply/` | Candidate only | Candidate applies to an active job (`job_id`, optional `cover_note`). Duplicate applications rejected with `400 Bad Request`. |
| `GET` | `/api/v1/applications/<uuid:pk>/` | Candidate, Employer, Admin | Retrieves application detail. Object-level IDOR check enforces access (`403 Forbidden` on unauthorized lookup). |
| `PATCH` | `/api/v1/applications/<uuid:pk>/` | Employer, Admin | Updates status (`employer_shortlisted`, `rejected`). Advancing to shortlisted triggers mutual fit if candidate is interested. |

### Job Leads (`/api/v1/job-leads/`)

| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/v1/job-leads/` | Admin only | Returns saved/archived leads with optional `?query=` and `?country=` filters. Non-admins receive `403 Forbidden`. |
| `POST` | `/api/v1/job-leads/` | Admin only | Allows admin to save or ingest a job lead. |

---

## 4. Permissions & Security / IDOR Protection

1. **Candidate Security**:
   - Filter query: `candidate_profile__user = request.user`.
   - Cannot view or apply using another candidate's profile.
   - Prohibited from modifying employer review fields or recruiter notes (`403 Forbidden`).
   - Prohibited from accessing job leads API (`403 Forbidden`).
2. **Employer Security**:
   - Filter query: `job__posted_by = request.user` or `job__company__owner = request.user`.
   - Cannot view applications for another employer's jobs (`403 Forbidden`).
   - Cannot modify candidate-owned information.
3. **Duplicate Protection**:
   - Enforced by database constraint `models.UniqueConstraint(fields=["candidate_profile", "job"])` and service layer pre-validation in `ApplyView`.

---

## 5. Test Results

### Phase 17 Dedicated Test Suite (`scripts/test-phase17-applications.mjs`)
- **37/37 PASSED (100%)**
  - Candidate 1, Candidate 2, Employer 1, Employer 2, Admin registration and login
  - Candidate profile setup with valid choice fields
  - Employer company and active job creation
  - Candidate 1 applies to active job $\to$ HTTP 201 (`candidate_interested`)
  - Duplicate application rejected $\to$ HTTP 400 with "already applied" error
  - Candidate 1 lists and views own application detail $\to$ HTTP 200
  - Candidate 2 lists applications $\to$ receives 0 applications
  - Candidate 2 denied Candidate 1 application detail $\to$ HTTP 403 (IDOR)
  - Employer 1 lists applications $\to$ sees Candidate 1 application
  - Employer 1 shortlists application $\to$ advances status to `mutual_fit`
  - Employer 2 denied Employer 1 application detail $\to$ HTTP 403 (IDOR)
  - Admin lists and filters applications $\to$ sees active applications
  - Admin creates and lists Job Leads $\to$ HTTP 201 & HTTP 200
  - Candidate denied Job Leads API $\to$ HTTP 403

### Regression Test Suite
- **Django Unit Tests (`python manage.py test`)**: **104/104 PASSED** (5 new Phase 17 unit tests added)
- **Django System Check (`python manage.py check`)**: **0 issues identified**
- **Phase 12 Auth Integration**: **16/16 PASSED**
- **Phase 13 Companies & Candidates Integration**: **29/29 PASSED**
- **Phase 14 Jobs Integration**: **31/31 PASSED**
- **Phase 15 Matches Integration**: **36/36 PASSED**
- **Phase 16 Handoffs Integration**: **38/38 PASSED**
- **Next.js Production Build (`npm run build`)**: **56/56 routes compiled successfully**

---

## 6. Production Safety & Invariants

- **Supabase production records modified**: NO
- **Supabase Auth modified**: NO
- **Supabase Storage modified**: NO
- **Production deployment performed**: NO
- **Supabase fallback active**: YES
- **External job provider fabricated**: NO
- **AI matching modified**: NO (deterministic formula preserved: `round(skill_score * 0.7 + exp_score * 0.3)`)
