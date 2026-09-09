# PHASE 21 — FULL SUPABASE FINAL RE-AUDIT

Date: September 9, 2026
Objective: Exhaustively scan repository for all remaining Supabase references, categorize them, and define clear deprecation targets.

---

## 1. Summary of References by Category

| Category | Description | Count | Action in Phase 21 |
| :--- | :--- | :--- | :--- |
| **Category A: Active Runtime Dependencies** | Code paths still executing direct Supabase queries/auth/storage in production | **1** (`src/app/api/roles/route.ts`) | Migrate to Django REST API `POST /api/v1/role-submissions/` |
| **Category B: Django-First Fallback Blocks** | Supabase fallback blocks kept during Phases 12–20 when Django was primary | **18 files** | Remove fallbacks now that Django APIs are proven 100% stable |
| **Category C: Dead / Unused Code** | Legacy files unreferenced in modern Django-first flow (`src/lib/match-runner.ts`, `recruiter-alert.ts`, etc.) | **5 files** | Clean up / safely remove |
| **Category D: Migration Tooling** | ETL command `migrate_supabase_to_postgres.py` | **1 file** | Preserve for historical provenance or archive |
| **Category E: Documentation & Tests** | Markdown phase guides, architecture docs, comments, package lock | Reference only | Keep historical docs, clean `package.json` |

---

## 2. Detailed Reference Manifest

### Category A: Active Runtime Dependency
1. `src/app/api/roles/route.ts`:
   - Still queries `supabase.from("role_submissions").insert(row)` directly.
   - **Remedy**: Create `RoleSubmission` model in Django, serializer, view, and route `POST /api/v1/role-submissions/`. Update Next.js route to proxy to Django.

### Category B: Django-First Fallbacks
1. `src/lib/auth.ts`: Legacy Supabase Auth session checks inside fallback blocks.
2. `src/lib/auth-actions.ts`: Supabase password reset / auth action fallbacks.
3. `src/middleware.ts`: Fallback to Supabase SSR cookie validation if Django JWT cookies are missing.
4. `src/lib/admin-create-candidate.ts`: `supabase.auth.admin.createUser` and `supabase.storage` fallbacks.
5. `src/app/admin/candidates/page.tsx`: Fallback to Supabase `candidate_profiles` query if Django fails.
6. `src/app/admin/jobs/page.tsx`: Fallback to Supabase `jobs` query if Django fails.
7. `src/app/admin/jobs/new/page.tsx`: Fallback to Supabase `companies` query if Django fails.
8. `src/app/admin/matches/page.tsx`: Fallback to Supabase `matches` query.
9. `src/app/admin/handoffs/page.tsx`: Fallback to Supabase `handoff_requests` query.
10. `src/app/api/candidate/resume/route.ts`: Fallback to Supabase storage.
11. `src/app/api/employer/logo/route.ts`: Fallback to Supabase storage.
12. `src/app/api/admin/candidates/[id]/resume/route.ts`: Fallback to Supabase storage.
13. `src/app/api/admin/jobs/route.ts`: Fallback to Supabase insert.
14. `src/app/api/jobs/route.ts`: Fallback to Supabase insert/query.
15. `src/app/api/matches/route.ts`: Fallback to Supabase insert/query.
16. `src/app/api/employer/company/route.ts`: Fallback to Supabase insert/query.
17. `src/app/api/candidate/profile/route.ts`: Fallback to Supabase insert/query.
18. `src/lib/admin-dashboard.ts`: Fallback to Supabase admin client for stats.

### Category C: Dead / Legacy Code
1. `src/lib/match-runner.ts`: Supabase-based client-side match runner (replaced by Django Celery & service matching).
2. `src/lib/recruiter-alert.ts`: Supabase-based email alerts (replaced by Django tasks).
3. `src/lib/job-notifications.ts`: Supabase-based notifications.
4. `src/lib/ensure-profile.ts`: Supabase profile creation utility.
5. `src/lib/public-talent.ts`: Supabase public card retrieval (replaced by Django candidate view).

### Category D: Migration Tooling
1. `backend/common/management/commands/migrate_supabase_to_postgres.py`:
   - Historical one-time ETL script used in Phases 3A-10. Kept for audit trail.

---

## 3. Plan of Execution for Phase 21 Cutover
1. Implement Django `POST /api/v1/role-submissions/` and migrate Next.js `src/app/api/roles/route.ts`.
2. Clean up Category B fallbacks to make Django the sole authoritative backend.
3. Clean up Category C dead files.
4. Remove `src/lib/supabase/` and uninstall `@supabase/supabase-js` and `@supabase/ssr` from `package.json`.
5. Run full test suites (Phases 12–21) and Next.js build to guarantee 0 regressions.
