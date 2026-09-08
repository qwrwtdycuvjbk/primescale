# Next.js → Supabase Dependency Inventory & Phase 7 Migration Mapping

## 1. Overview
This document catalogs every Supabase dependency currently present in the Next.js frontend, classifies them by domain, maps them to their respective Django REST Framework endpoints (implemented in Phases 2–6), and tracks their migration status for Phase 7.

---

## 2. Classification Summary
- **Category A (Authentication)**: 12 references (login, signup, session, OAuth, redirect, token handling). **Retained on Supabase Auth** in Phase 7 to prevent production disruption.
- **Category B (Database / Core Domain)**: 36 references across Jobs, Companies, Candidate Profiles, Matches, Handoffs. **Mapped to Django REST API**.
- **Category C (Storage)**: 4 references (resumes, company logos). **Mapped to Django S3 Storage API**.
- **Category D (Supabase RPC)**: 1 reference (`ensure_user_profile` in `src/lib/ensure-profile.ts`). Managed during profile creation; in Django, handled via `UserRegistrationSerializer` & `CurrentUserView`.
- **Category E (Realtime / Subscriptions)**: 0 references found (`channel`, `postgres_changes`, etc. are not used).

---

## 3. Comprehensive Inventory & Endpoint Mapping

| File / Component | Function / Usage | Supabase Service | Table / Bucket | Operation | Django REST Replacement | Phase 7 Status |
|---|---|---|---|---|---|---|
| `src/lib/public-talent.ts` | `getPublicTalentShowcase()` | Database | `candidate_profiles` | `SELECT` | `GET /api/v1/candidates/public-showcase/` | Django Ready |
| `src/app/api/jobs/route.ts` | `POST()` (Create job) | Database | `jobs` | `INSERT` | `POST /api/v1/jobs/` | Django Ready |
| `src/app/api/jobs/[id]/route.ts` | `PATCH()` (Update job status) | Database | `jobs` | `UPDATE` | `PATCH /api/v1/jobs/<id>/` | Django Ready |
| `src/app/api/jobs/[id]/duplicate/route.ts` | `POST()` (Duplicate job) | Database | `jobs` | `SELECT + INSERT` | `POST /api/v1/jobs/<id>/duplicate/` | Django Ready |
| `src/app/api/employer/company/route.ts` | `POST()` (Save company) | Database | `companies`, `company_members` | `INSERT/UPDATE` | `POST /api/v1/companies/me/` | Django Ready |
| `src/app/api/employer/logo/route.ts` | `POST()` (Upload logo) | Storage | `company-logos` | `upload` + `getPublicUrl` | `POST /api/v1/companies/me/logo/` | Django Ready |
| `src/app/api/candidate/profile/route.ts` | `POST()` (Save candidate) | Database | `candidate_profiles` | `INSERT/UPDATE` | `POST /api/v1/candidates/me/` | Django Ready |
| `src/app/api/candidate/resume/route.ts` | `POST()` (Upload resume) | Storage | `resumes` | `upload` + `getPublicUrl` | `POST /api/v1/candidates/me/resume/` | Django Ready |
| `src/app/api/matches/route.ts` | `PATCH()` (Update match) | Database | `matches` | `UPDATE` | `PATCH /api/v1/matches/<id>/` | Django Ready |
| `src/app/api/admin/handoffs/[id]/route.ts` | `PATCH()` (Update handoff) | Database | `handoff_requests` | `UPDATE` | `PATCH /api/v1/handoffs/<id>/` | Django Ready |
| `src/lib/admin-dashboard.ts` | `loadAdminNavCounts()` | Database | `matches`, `handoff_requests` | `SELECT count` | `GET /api/v1/matches/`, `GET /api/v1/handoffs/` | Django Ready |
| `src/lib/admin-dashboard.ts` | `loadAdminDashboardStats()` | Database | `matches`, `handoffs`, `jobs`, `candidates` | `SELECT stats` | Django aggregated dashboard endpoints | Django Ready |
| `src/app/candidate/page.tsx` | Dashboard stats & recent matches | Database | `candidate_profiles`, `matches` | `SELECT` | `GET /api/v1/candidates/me/`, `GET /api/v1/matches/` | Django Ready |
| `src/app/candidate/matches/page.tsx` | Candidate matches list | Database | `matches` | `SELECT` | `GET /api/v1/matches/` | Django Ready |
| `src/app/employer/page.tsx` | Employer dashboard stats & roles | Database | `companies`, `jobs`, `matches` | `SELECT` | `GET /api/v1/companies/me/`, `GET /api/v1/jobs/?view=my_company`, `GET /api/v1/matches/` | Django Ready |
| `src/app/employer/jobs/page.tsx` | Employer job listings | Database | `jobs` | `SELECT` | `GET /api/v1/jobs/?view=my_company` | Django Ready |
| `src/app/employer/matches/page.tsx` | Employer matches list | Database | `matches` | `SELECT` | `GET /api/v1/matches/` | Django Ready |
| `src/app/admin/matches/page.tsx` | Admin match review queue | Database | `matches` | `SELECT` | `GET /api/v1/matches/?visible_to_employer=false` | Django Ready |
| `src/app/admin/handoffs/page.tsx` | Admin handoffs queue | Database | `handoff_requests` | `SELECT` | `GET /api/v1/handoffs/` | Django Ready |
| `src/lib/auth.ts` | `getSessionProfile()`, `requireRole()` | Auth & DB | `profiles`, `auth.users` | `getUser`, `select` | Retained on Supabase Auth (Phase 7) | Retained |
| `src/middleware.ts` | Route protection | Auth | `auth.users` | `getUser` | Retained on Supabase Auth (Phase 7) | Retained |
| `src/app/auth/callback/route.ts` | OAuth / PKCE exchange | Auth | `auth` | `exchangeCodeForSession` | Retained on Supabase Auth (Phase 7) | Retained |
| `src/app/auth/confirm/route.ts` | Email verification | Auth | `auth` | `verifyOtp` | Retained on Supabase Auth (Phase 7) | Retained |
| `src/app/api/auth/login/route.ts` | Password login | Auth | `auth` | `signInWithPassword` | Retained on Supabase Auth (Phase 7) | Retained |
| `src/app/api/auth/complete-login/route.ts`| Post-login routing | Auth & DB | `profiles` | `upsert` | Retained on Supabase Auth (Phase 7) | Retained |

---

## 4. Architectural Rules for Phase 7
1. **Zero Frontend Redesign**: CSS, HTML structure, animations, and Tailwind tokens remain 100% identical.
2. **Centralized API Client**: Created under `src/lib/api/` with typed methods for Django REST calls, automatic base URL resolution (`process.env.NEXT_PUBLIC_API_URL` with local fallback), and robust error handling.
3. **No Duplicate Business Logic**: Scoring, handoff state transitions, and file upload validations are performed exclusively on Django.
4. **Safe Fallback**: If an unmigrated feature is visited, Supabase fallback continues operating without disruption.
