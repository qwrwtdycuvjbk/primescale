# People Remotely — Architectural Transition Document

## Current Architecture

```
Browser
   ↓
Next.js 16 (App Router)
   ↓
Next.js Server Actions / API Routes
   ↓
Supabase Auth  |  Supabase PostgreSQL  |  Supabase Storage  |  OpenAI  |  Resend  |  OpenWeb Ninja
```

---

## Target Architecture

```
Browser
   ↓
Next.js 16 Frontend (Port 3000)
   ↓
HTTP REST API (http://localhost:8000/api/v1/)
   ↓
Django REST Framework (Port 8000)
   ↓
PostgreSQL Database

Django Backend Architecture:
   ├── PostgreSQL (Data persistence)
   ├── Redis → Celery Workers (Async match runner, email, bulk CSV import)
   ├── AWS S3 (Resumes - presigned URLs, Company Logos - public bucket)
   ├── OpenAI API (gpt-4o-mini match reasons & JD parsing)
   ├── Resend API (Transactional ops email notifications)
   └── OpenWeb Ninja JSearch API (External job lead discovery)
```

---

## Supabase Schema to Django Model Mapping

| Supabase Table | Django Model | App | Description |
|---|---|---|---|
| `auth.users` + `public.profiles` | `accounts.User` | `accounts` | Merged custom user model with `email`, `role`, `full_name`, `phone` |
| `public.companies` | `companies.Company` | `companies` | Company profiles owned by employer users |
| `public.company_members` | `companies.CompanyMember` | `companies` | Membership mapping with `unique(company, user)` |
| `public.candidate_profiles` | `candidates.CandidateProfile` | `candidates` | Candidate profiles (`OneToOne` with `User`), JSON field for skills |
| `public.jobs` | `jobs.Job` | `jobs` | Job postings linked to `Company` and `User` |
| `public.matches` | `matching.Match` | `matching` | Candidate & Job scoring, `unique(candidate_profile, job)` |
| `public.handoff_requests` | `handoffs.HandoffRequest` | `handoffs` | Mutual-fit recruiter handoff queue |

---

## Applications Table Assessment

[CONFIRMED] Based on exact source code and SQL inspection:
- There is **no `applications` table** in the Supabase PostgreSQL database schema or migration scripts.
- Candidate interest and applications are modeled using `matches.status`:
  - `suggested` -> `candidate_interested` / `employer_shortlisted` -> `mutual_fit` -> `handoff_requests`
- Therefore, no separate `Application` model was created, avoiding unnecessary DB complexity while accurately preserving the existing workflow.
