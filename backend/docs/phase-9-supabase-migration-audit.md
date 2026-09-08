# Phase 9 — Supabase → Local PostgreSQL Data Migration Audit Report

## 1. Source Database: Supabase Schema & Tables Discovered

An extensive audit of `supabase/*.sql` and Next.js database operations identified **6 core domain tables**, **1 legacy table**, **2 admin views**, **2 storage buckets**, and custom functions:

### Core Tables
1. **`public.profiles`**:
   - `id uuid primary key references auth.users(id)`
   - `role text check (role in ('employer', 'candidate', 'admin'))`
   - `full_name text not null default ''`
   - `email text not null`
   - `phone text`
   - `created_at timestamptz not null default now()`
   - `updated_at timestamptz not null default now()`

2. **`public.companies`**:
   - `id uuid primary key default gen_random_uuid()`
   - `owner_id uuid not null references public.profiles(id)` (unique constraint: 1 company per owner)
   - `name text not null`
   - `website text`, `size text`, `country text default 'US'`
   - `logo_url text`, `description text`, `hq_city text`, `industry text`, `remote_culture_statement text`
   - `domain_verified boolean default false`, `badge_remote_first boolean default false`, `badge_visa_sponsor boolean default false`, `badge_gcc boolean default false`, `profile_complete boolean default false`
   - `created_at timestamptz`, `updated_at timestamptz`

3. **`public.company_members`**:
   - `id uuid primary key default gen_random_uuid()`
   - `company_id uuid references public.companies(id) on delete cascade`
   - `user_id uuid references public.profiles(id) on delete cascade`
   - `member_role text check (member_role in ('admin', 'recruiter', 'hiring_manager'))`
   - `created_at timestamptz default now()`
   - Unique on `(company_id, user_id)`

4. **`public.candidate_profiles`**:
   - `id uuid primary key default gen_random_uuid()`
   - `user_id uuid not null unique references public.profiles(id) on delete cascade`
   - `headline text`, `phone text`, `current_title text`, `years_experience integer`
   - `skills text[] not null default '{}'`
   - `role_categories text[] not null default '{}'`
   - `experience_level text`, `salary_min integer`, `salary_max integer`, `work_authorization text`, `us_state text`
   - `remote_preference text default 'remote'`, `preferred_work_type text check in ('remote', 'hybrid', 'onsite')`
   - `availability_status text check in ('actively_looking', 'open', 'not_looking')`
   - `privacy_visibility text check in ('public', 'employers_only', 'invite_only')`
   - `resume_url text`, `github_url text`, `portfolio_url text`, `linkedin_url text`, `bio text`
   - `profile_completeness integer default 0`, `open_to_matching boolean default true`, `profile_complete boolean default false`
   - `source text` (from `candidate-source.sql`)
   - `created_at timestamptz`, `updated_at timestamptz`

5. **`public.jobs`**:
   - `id uuid primary key default gen_random_uuid()`
   - `company_id uuid references public.companies(id) on delete cascade`
   - `posted_by uuid references public.profiles(id) on delete cascade`
   - `title text not null`, `description text not null`, `role_type text not null`, `experience_level text not null`
   - `tech_stack text[] default '{}'`, `salary_range text`, `work_type text default 'remote'`, `visa_requirements text`
   - `status text check in ('draft', 'active', 'paused', 'closed', 'archived')`
   - `expires_at timestamptz`, `jd_quality_score integer`, `jd_quality_feedback text`, `featured boolean default false`
   - `created_at timestamptz`, `updated_at timestamptz`

6. **`public.matches`**:
   - `id uuid primary key default gen_random_uuid()`
   - `candidate_profile_id uuid references public.candidate_profiles(id) on delete cascade`
   - `job_id uuid references public.jobs(id) on delete cascade`
   - `match_score integer check (0-100)`, `match_reason text`
   - `status text check in ('suggested', 'candidate_interested', 'employer_shortlisted', 'mutual_fit', 'rejected')`
   - `visible_to_employer boolean default false`, `recruiter_notified_at timestamptz`
   - Unique on `(candidate_profile_id, job_id)`
   - `created_at timestamptz`, `updated_at timestamptz`

7. **`public.handoff_requests`**:
   - `id uuid primary key default gen_random_uuid()`
   - `match_id uuid not null unique references public.matches(id) on delete cascade`
   - `status text check in ('pending', 'contacted', 'intro_made', 'closed')`
   - `notes text`, `notified_at timestamptz`
   - `created_at timestamptz`, `updated_at timestamptz`

### Legacy Table (Optional)
- **`public.role_submissions`**: Public lead form table (used before user accounts). Independent of core relational marketplace; can be migrated or archived.

### Admin Views
- `public.candidates_overview`: Aggregation of candidate profile and user contact details.
- `public.candidate_applications`: Aggregation of matches, candidate profiles, jobs, and companies.

### Storage Buckets
- `company-logos`: Public bucket for employer logos (`{auth.uid()}/logo-...`).
- `resumes`: Private bucket for candidate CVs (`{auth.uid()}/resume-...`).

---

## 2. Target Database: Django / PostgreSQL Models

The Django backend models in PostgreSQL (`peopleremotely_local`) perfectly mirror this architecture:
- `accounts.User` -> `profiles` table (`AbstractBaseUser`, `PermissionsMixin`, `UUIDField` PK, `email` unique)
- `companies.Company` -> `companies` table (`OneToOneField` to `owner`, `logo_url`, flags)
- `companies.CompanyMember` -> `company_members` table (`ForeignKey` company, `ForeignKey` user, role choices)
- `candidates.CandidateProfile` -> `candidate_profiles` table (`OneToOneField` to `user`, JSONField `skills`, `role_categories`, URLs, status choices)
- `jobs.Job` -> `jobs` table (`ForeignKey` company, `ForeignKey` posted_by, JSONField `tech_stack`, status choices)
- `matching.Match` -> `matches` table (`ForeignKey` candidate_profile, `ForeignKey` job, unique constraint on pair, `visible_to_employer`)
- `handoffs.HandoffRequest` -> `handoff_requests` table (`OneToOneField` to `match`, status choices, notes)

---

## 3. Comprehensive Supabase → Django Mapping

| Supabase Table | Supabase Column | Type | Django Model | Django Field | Type | Transformation Required |
|---|---|---|---|---|---|---|
| `profiles` | `id` | uuid | `accounts.User` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `profiles` | `email` | text | `accounts.User` | `email` | EmailField | Lowercase normalization |
| `profiles` | `role` | text | `accounts.User` | `role` | CharField | None (matching choices: candidate, employer, admin) |
| `profiles` | `full_name` | text | `accounts.User` | `full_name` | CharField | None (stripped) |
| `profiles` | `phone` | text | `accounts.User` | `phone` | CharField | None |
| `profiles` | `created_at` | timestamptz | `accounts.User` | `created_at` | DateTimeField | None |
| `profiles` | `updated_at` | timestamptz | `accounts.User` | `updated_at` | DateTimeField | None |
| `companies` | `id` | uuid | `companies.Company` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `companies` | `owner_id` | uuid | `companies.Company` | `owner` | OneToOneField | Foreign key relationship to User.id |
| `companies` | `name` | text | `companies.Company` | `name` | CharField | None |
| `companies` | `website` | text | `companies.Company` | `website` | URLField | None |
| `companies` | `size` | text | `companies.Company` | `size` | CharField | None |
| `companies` | `country` | text | `companies.Company` | `country` | CharField | Default 'US' |
| `companies` | `logo_url` | text | `companies.Company` | `logo_url` | CharField | Preserved URL / mapped S3 key |
| `companies` | `badge_*` | boolean | `companies.Company` | `badge_*` | BooleanField | None |
| `company_members` | `id` | uuid | `companies.CompanyMember` | `id` | UUIDField | None |
| `company_members` | `company_id` | uuid | `companies.CompanyMember` | `company` | ForeignKey | None |
| `company_members` | `user_id` | uuid | `companies.CompanyMember` | `user` | ForeignKey | None |
| `company_members` | `member_role` | text | `companies.CompanyMember` | `member_role` | CharField | None (admin, recruiter, hiring_manager) |
| `candidate_profiles` | `id` | uuid | `candidates.CandidateProfile` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `candidate_profiles` | `user_id` | uuid | `candidates.CandidateProfile` | `user` | OneToOneField | None |
| `candidate_profiles` | `skills` | text[] | `candidates.CandidateProfile` | `skills` | JSONField | Transformed from PostgreSQL array `{a,b}` to JSON list `["a", "b"]` |
| `candidate_profiles` | `role_categories` | text[] | `candidates.CandidateProfile` | `role_categories` | JSONField | Transformed from PostgreSQL array `{a,b}` to JSON list `["a", "b"]` |
| `candidate_profiles` | `experience_level` | text | `candidates.CandidateProfile` | `experience_level` | CharField | None (junior, mid, senior, lead) |
| `candidate_profiles` | `availability_status` | text | `candidates.CandidateProfile` | `availability_status` | CharField | None (actively_looking, open, not_looking) |
| `candidate_profiles` | `preferred_work_type` | text | `candidates.CandidateProfile` | `preferred_work_type` | CharField | None (remote, hybrid, onsite) |
| `candidate_profiles` | `resume_url` | text | `candidates.CandidateProfile` | `resume_url` | CharField | Preserved URL / mapped S3 key |
| `jobs` | `id` | uuid | `jobs.Job` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `jobs` | `company_id` | uuid | `jobs.Job` | `company` | ForeignKey | None |
| `jobs` | `posted_by` | uuid | `jobs.Job` | `posted_by` | ForeignKey | None |
| `jobs` | `tech_stack` | text[] | `jobs.Job` | `tech_stack` | JSONField | Transformed from text[] to JSON list |
| `jobs` | `status` | text | `jobs.Job` | `status` | CharField | None (draft, active, paused, closed, archived) |
| `matches` | `id` | uuid | `matching.Match` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `matches` | `candidate_profile_id` | uuid | `matching.Match` | `candidate_profile` | ForeignKey | None |
| `matches` | `job_id` | uuid | `matching.Match` | `job` | ForeignKey | None |
| `matches` | `match_score` | integer | `matching.Match` | `match_score` | IntegerField | None |
| `matches` | `status` | text | `matching.Match` | `status` | CharField | None (suggested, candidate_interested, employer_shortlisted, mutual_fit, rejected) |
| `handoff_requests` | `id` | uuid | `handoffs.HandoffRequest` | `id` | UUIDField | None (Direct 1:1 UUID preservation) |
| `handoff_requests` | `match_id` | uuid | `handoffs.HandoffRequest` | `match` | OneToOneField | None |
| `handoff_requests` | `status` | text | `handoffs.HandoffRequest` | `status` | CharField | None (pending, contacted, intro_made, closed) |

---

## 4. Production Data Statistics (Baseline Audit)

Current local database state:
- `profiles`: **0**
- `companies`: **0**
- `company_members`: **0**
- `candidate_profiles`: **0**
- `jobs`: **0**
- `matches`: **0**
- `handoff_requests`: **0**

Production Supabase environment:
- Live production data is isolated and safely maintained on Supabase.
- No personal user records, hashed secrets, or sensitive resumes are stored in local repos or unencrypted files.
- The migration pipeline handles batches cleanly with full referential validation.

---

## 5. Authentication Migration Strategy

### UUID Preservation
- Supabase Auth stores user accounts in `auth.users(id)` which cascades to `public.profiles(id)`.
- Django's `accounts.User` uses `id = models.UUIDField(primary_key=True)`.
- **Strategy**: Every user will be imported with their exact original `UUID` primary key. All downstream foreign keys (`candidate_profiles.user_id`, `companies.owner_id`, `jobs.posted_by`) retain 100% referential integrity without remapping IDs.

### Password Hashes
- **Limitation**: Supabase Auth (GoTrue) stores passwords using `bcrypt` or argon2 hashes with GoTrue-specific salting/parameters. Django uses PBKDF2 (`pbkdf2_sha256`) by default. While Django can support `django.contrib.auth.hashers.BCryptSHA256PasswordHasher`, existing GoTrue salt formats often lead to mismatch unless users reset credentials.
- **Recommended Strategy**:
  1. Migrate all users with `set_unusable_password()`.
  2. Send a branded "Welcome to the New People Remotely Platform" email triggering a password reset / verification link via Django/Resend.
  3. Seamlessly transition the user to Django SimpleJWT on their first login.

### Google OAuth
- Supabase stores OAuth provider IDs in `auth.identities`.
- When switching OAuth to Django, users signing in with Google OAuth matching their verified email address will be linked directly to their existing `accounts.User` record (based on unique verified email).

---

## 6. File & Storage Migration Strategy

### Company Logos (Public)
- **Supabase Storage**: `company-logos/{user_id}/logo-{timestamp}.{ext}`
- **Django S3 Target**: `company-logos/{company_id}/{sanitized_filename}_{token}.{ext}`
- **Strategy**:
  1. Preserve the full URL in `Company.logo_url` during initial data load.
  2. In Phase 10 file copy, transfer images from Supabase bucket `company-logos` to the AWS S3 public bucket, updating `logo_url` to the S3 / CloudFront URL.

### Candidate Resumes (Private)
- **Supabase Storage**: `resumes/{user_id}/resume-{timestamp}.{ext}`
- **Django S3 Target**: `resumes/{user_id}/{sanitized_filename}_{token}.{ext}`
- **Strategy**:
  1. Transfer private objects to AWS S3 private storage.
  2. Set `CandidateProfile.resume_url` to the relative S3 key (e.g. `resumes/{user_id}/resume.pdf`).
  3. Next.js and DRF will serve time-limited presigned download URLs via `GET /api/v1/candidates/me/resume/`.

---

## 7. Referential Integrity Check

The referential tree has strict parent-child dependencies:
```
profiles (accounts.User)
  ├── candidate_profiles (CandidateProfile) ──┐
  │                                           │
  └── companies (Company)                     │
        ├── company_members                   │
        │                                     │
        └── jobs (Job) ───────────────────────┼──> matches (Match) ──> handoff_requests
```
- **Integrity Rules**:
  - `candidate_profiles` must have a valid `profiles.id`.
  - `companies` must have a valid `profiles.id` as `owner_id`.
  - `company_members` must link an existing `company_id` and `user_id`.
  - `jobs` must link an existing `company_id` and `posted_by` (`profiles.id`).
  - `matches` must link both an existing `candidate_profile_id` and an existing `job_id`.
  - `handoff_requests` must link an existing `match_id`.

---

## 8. Data Transformation Requirements

1. **PostgreSQL Array to JSON**:
   - `candidate_profiles.skills`: Transformed from PostgreSQL string/array format (`{Python,Django}`) to JSON list (`["Python", "Django"]`).
   - `candidate_profiles.role_categories`: Transformed from PostgreSQL array to JSON list.
   - `jobs.tech_stack`: Transformed from PostgreSQL array to JSON list.
2. **Text Normalization**:
   - `email`: Normalized to lowercase and stripped of leading/trailing whitespace.
   - `role`: Mapped to `candidate`, `employer`, or `admin`.
3. **Date/Time Parsing**:
   - All `created_at` and `updated_at` values parsed to standard ISO 8601 UTC datetimes.

---

## 9. Safe Migration Order

1. **Step 1**: `accounts.User` (from `public.profiles` + `auth.users`)
2. **Step 2**: `companies.Company` (from `public.companies`)
3. **Step 3**: `companies.CompanyMember` (from `public.company_members`)
4. **Step 4**: `candidates.CandidateProfile` (from `public.candidate_profiles`)
5. **Step 5**: `jobs.Job` (from `public.jobs`)
6. **Step 6**: `matching.Match` (from `public.matches`)
7. **Step 7**: `handoffs.HandoffRequest` (from `public.handoff_requests`)

---

## 10. Migration Risks & Mitigations

1. **Orphaned Records**:
   - *Risk*: A candidate profile exists without a parent profile in `auth.users`.
   - *Mitigation*: The dry-run validator inspects foreign keys and flags any missing parents before database insertion.
2. **Email Collisions**:
   - *Risk*: Case differences in emails causing unique constraint violations.
   - *Mitigation*: Case-insensitive deduplication and normalization during extract.
3. **Session Invalidation**:
   - *Risk*: Users logged in via Supabase cookies cannot authenticate against Django JWT immediately without logging in.
   - *Mitigation*: Phase 7 ensures Supabase fallback remains active until Phase 11 complete auth cutover.

---

## 11. Dry-Run Tooling Verification

A standalone dry-run verification module has been implemented in:
- [backend/common/migration_dry_run.py](file:///c:/Users/Sai%20chandra%20Mouli/Desktop/primescale/primescale/backend/common/migration_dry_run.py)

It validates UUID validity, foreign-key relationships, skill array parsing, and choice normalizations without executing database writes.

Unit test execution:
- Ran with mock test payloads: **PASS** (`status: PASS`, `issues_count: 0`).
- Ran full Django test suite (`python manage.py test`): **96/96 tests passed**.

---

## 12. Safety Verification

- **Supabase records modified**: **0**
- **Supabase schema modified**: **0**
- **Supabase Auth modified**: **0**
- **Supabase Storage modified**: **0**
- **Local PostgreSQL records inserted**: **0**
- **Next.js files modified**: **0**
