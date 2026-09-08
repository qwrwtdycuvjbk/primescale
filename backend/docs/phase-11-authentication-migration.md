# Phase 11 — Django Authentication Migration & Cutover Report

## 1. Executive Summary

In **Phase 11**, the Django REST Framework authentication and authorization system was fully upgraded and verified to support migrated production users and new registrants.

Key milestones achieved:
- **Zero Production Disruption**: Supabase Auth remains 100% active, untouched, and un-modified. Next.js production frontend remains intact without premature cutover.
- **Migrated User Account Claim Flow**: Migrated users (who carry `set_unusable_password()`) can claim their accounts and set valid Django passwords using secure, single-use, time-limited password reset tokens (`POST /api/v1/auth/password-reset/` & `POST /api/v1/auth/password-reset-confirm/`).
- **UUID Preservation**: Migrated user UUIDs remain immutable (`accounts.User.id == Supabase auth.users.id`).
- **Google OAuth & Account Linking**: `POST /api/v1/auth/oauth/google/` links existing users by email without creating duplicates or modifying UUIDs.
- **Email Verification Flow**: Secure, time-limited verification tokens via `POST /api/v1/auth/verify-email/` and `POST /api/v1/auth/resend-verification/`.
- **JWT & Cookie Architecture**: SimpleJWT HS256 tokens paired with `HttpOnly`, `SameSite=Lax`, `Secure` cookies for Next.js App Router / middleware compatibility.
- **Test Results**: **110/110 tests passed** (96 existing tests + 14 new Phase 11 security & flow tests).

---

## 2. Architecture Comparison: Supabase Auth vs. Django Auth

```
========================================================================================================================
CURRENT ARCHITECTURE (ACTIVE IN PRODUCTION)          NEW DJANGO ARCHITECTURE (LOCAL & PREPARED)
========================================================================================================================
Browser                                              Browser
   ↓                                                    ↓ (HttpOnly Cookies & Bearer Tokens)
Next.js 16 (Port 3000)                                Next.js 16 (Port 3000)
   ↓                                                    ↓
Supabase Auth (GoTrue + Cookies)                      Django REST Framework (Port 8000)
   ↓                                                    ↓
Supabase auth.users + public.profiles                 Django accounts.User (PostgreSQL profiles table)
========================================================================================================================
```

### Detailed Component Mapping

| Feature | Supabase Auth (Current) | Django REST Framework (Target) |
|---|---|---|
| User Model & Table | `auth.users` + `public.profiles` | `accounts.User` (`profiles` table, UUID PK) |
| Authentication Type | GoTrue JWT + Session cookies | SimpleJWT (HS256) + HttpOnly cookies |
| Token Rotation | Handled by GoTrue client | `ROTATE_REFRESH_TOKENS = True` with Blacklist |
| Password Hashing | Supabase bcrypt | Django PBKDF2 with SHA-256 (870,000 iterations) |
| Password Reset | Supabase email link (`/auth/confirm`) | HMAC single-use token (`/password-reset-confirm/`) |
| Email Verification | Supabase OTP / verifyOtp | Token generator (`/verify-email/`) |
| Google OAuth | Supabase `signInWithOAuth` | `POST /api/v1/auth/oauth/google/` with Account Linking |
| Session Storage | `@supabase/ssr` chunked cookies | `access_token` & `refresh_token` HttpOnly cookies |

---

## 3. Password Migration & Account Activation Strategy

### Problem
Supabase passwords are encrypted using GoTrue-specific bcrypt configurations. Blindly migrating or translating password hashes risks authentication failures or security vulnerabilities. During Phase 10, all migrated users were assigned unusable passwords via `user.set_unusable_password()`.

### Solution: Secure Welcome / Password Setup Flow
```text
Migrated User
     ↓
Visits Login Page
     ↓
Cannot log in with unusable password (HTTP 401)
     ↓
Enters Email at Password Reset / Claim Account
     ↓
POST /api/v1/auth/password-reset/
     ↓
Generates single-use, time-limited HMAC token based on user state & timestamp
Dispatches branded welcome/claim email via Resend/Celery
Returns HTTP 200 (Anti-enumeration: identical response if email doesn't exist)
     ↓
User clicks secure link in email
     ↓
POST /api/v1/auth/password-reset-confirm/
     ↓
Validates token and enforces Django password complexity validators
Executes user.set_password(new_password)
Sets email_verified = True
     ↓
Returns JWT tokens + sets HttpOnly cookies
User is fully authenticated with usable Django credentials
```

### Invalidation & Anti-Tampering
- The reset token includes the user's password hash in the HMAC calculation. Once `user.set_password()` is executed, the token is **immediately and permanently invalidated** (single-use guarantee).
- Malformed, expired, or tampered tokens are rejected with HTTP 400.

---

## 4. Email Verification Flow

1. **User Registration** (`POST /api/v1/auth/register/`):
   - Creates `accounts.User` with `email_verified = False`.
   - Dispatches verification email containing `uidb64` and HMAC verification token.
2. **Email Verification** (`POST /api/v1/auth/verify-email/`):
   - Validates `uid` and token via `email_verification_token_generator`.
   - Sets `user.email_verified = True`.
   - Hash changes upon verification, invalidating the token from future re-use.
3. **Resend Verification** (`POST /api/v1/auth/resend-verification/`):
   - Idempotently resends token if account exists and is unverified.
   - Suppresses enumeration.
4. **Migrated Production Users**:
   - Migrated users whose emails were already verified in Supabase retain verified status. Completing password reset also verifies email automatically.

---

## 5. Google OAuth & Account Linking Strategy

### Identification & Linking Flow
```text
Existing user email: candidate@test.com (UUID: 0e122df4-d903-4af3-88eb-c7a18dd24a9b)
                    ↓
Next.js Google Sign-In or Direct Token
                    ↓
POST /api/v1/auth/oauth/google/
{ "email": "candidate@test.com", "role": "candidate", "id_token": "..." }
                    ↓
Lookup: User.objects.filter(email=email).first()
                    ↓
User Found? ────────┬────────> YES: Link to existing account
                    │                 - Preserve exact UUID (0e122df4-...)
                    │                 - Ensure email_verified = True
                    │                 - Return JWT tokens + cookies (created=False)
                    │
                    └────────> NO:  Create new User
                                      - Set role = 'candidate' / 'employer'
                                      - Set unusable password (Google-only auth)
                                      - Return JWT tokens + cookies (created=True)
```

### Prevention of Duplicate Accounts
- If `migrated.candidate@example.com` already exists in PostgreSQL from the Supabase migration, a Google sign-in with that email **will not create a duplicate user**.
- The existing UUID and role are preserved, ensuring all foreign keys (`candidate_profiles`, `companies`, `matches`, `jobs`) remain intact.

---

## 6. JWT and Cookie Security Strategy

### SimpleJWT Configuration (`backend/config/settings.py`):
- `ACCESS_TOKEN_LIFETIME = 60 minutes`
- `REFRESH_TOKEN_LIFETIME = 7 days`
- `ROTATE_REFRESH_TOKENS = True` (Rotates refresh token upon every `/refresh/` call)
- `BLACKLIST_AFTER_ROTATION = True` (Revokes prior refresh tokens)
- `AUTH_HEADER_TYPES = ("Bearer",)`

### Cookie Strategy:
- **`access_token`**:
  - `HttpOnly`: True (inaccessible to JavaScript / immune to XSS)
  - `SameSite`: `"Lax"` (prevents CSRF while allowing top-level navigation)
  - `Secure`: True (enforced in production HTTPS)
  - `Path`: `/` (available across Next.js Server Components and middleware)
  - `Max-Age`: 3600 seconds (60m)
- **`refresh_token`**:
  - `HttpOnly`: True
  - `SameSite`: `"Lax"`
  - `Secure`: True
  - `Path`: `/api/v1/auth/` (scoped strictly to auth endpoints)
  - `Max-Age`: 604800 seconds (7 days)

---

## 7. Next.js Frontend Migration Inventory (Preparation for Phase 12)

The following inventory identifies all Next.js frontend files currently coupled to Supabase Auth and their planned Django API replacements:

| File Path | Current Supabase Mechanism | Planned Django Replacement |
|---|---|---|
| `src/middleware.ts` | `@supabase/ssr` `supabase.auth.getUser()` checking session cookies | Validate `access_token` cookie or query `/api/v1/auth/me/` |
| `src/lib/auth.ts` | `getSessionProfile()`, `requireRole()` using Supabase server client | Extract JWT from HttpOnly cookie, call `/api/v1/auth/me/` |
| `src/lib/ensure-profile.ts` | `ensureProfileForUser()` via Supabase RPC and profiles upsert | Deprecated; Django handles profile existence upon registration & OAuth |
| `src/components/auth/AuthGoogleSection.tsx` | `supabase.auth.signInWithOAuth({ provider: 'google' })` | Call Django Google OAuth `/api/v1/auth/oauth/google/` via Next.js route |
| `src/app/auth/callback/route.ts` | `supabase.auth.exchangeCodeForSession(code)` | Exchange Google code and forward verified token to Django OAuth endpoint |
| `src/app/auth/confirm/route.ts` | `supabase.auth.verifyOtp()` | Forward token to Django `/api/v1/auth/verify-email/` |
| `src/app/api/auth/login/route.ts` | `supabase.auth.signInWithPassword()` | Call `POST /api/v1/auth/login/`, receive and propagate HttpOnly cookies |
| `src/app/api/auth/complete-login/route.ts`| Updates profile role for admin | Controlled directly in Django via `accounts.User.role` |

---

## 8. Test Suite Summary

### Test Execution Counts:
- **Existing Django Tests**: 96 tests
- **New Phase 11 Tests**: 14 tests
- **Total Django Tests**: **110 tests**
- **Passed**: 110
- **Failed**: 0

### Breakdown of New Phase 11 Tests (`backend/accounts/test_phase11_auth.py`):
1. `test_migrated_user_initial_state`: Preserved UUID and unusable password verification.
2. `test_migrated_user_password_reset_flow`: End-to-end password reset, claim, and login.
3. `test_password_reset_anti_enumeration`: Nonexistent email security test.
4. `test_password_reset_single_use_token`: Invalidation of token after password change.
5. `test_password_reset_invalid_or_tampered_token`: Rejection of corrupted reset tokens.
6. `test_email_verification_flow`: Registration, verification token generation, and confirmation.
7. `test_email_verification_invalid_token`: Rejection of invalid verification tokens.
8. `test_resend_verification_endpoint`: Verification resend security test.
9. `test_google_oauth_links_existing_migrated_user`: Account linking without UUID changes or duplicate rows.
10. `test_google_oauth_new_user_creation`: New user onboarding via Google OAuth.
11. `test_cookie_flags_on_login`: Verification of HttpOnly, SameSite=Lax flags on response cookies.
12. `test_cookie_cleared_on_logout`: Verification of cookie clearing upon logout.
13. `test_unauthorized_me_endpoint`: HTTP 401 verification on unauthenticated profile access.
14. `test_admin_cannot_self_register`: Strict rejection of admin registration attempts.

---

## 9. Production Cutover Requirements (Phase 12 / Final Cutover)

Before disabling Supabase Auth in production:
1. **Frontend Authentication Switch**: Update Next.js App Router auth routes (`/api/auth/login`, `/auth/callback`, `middleware.ts`) to point to Django REST Framework.
2. **DNS & SSL Verification**: Ensure DRF backend has valid HTTPS domain configured for production secure cookies (`Secure=True`).
3. **Resend Email Templates**: Configure production Resend API keys and domain verification for sending password reset and verification emails.
4. **Google Cloud Console Credentials**: Add Django backend callback URLs to authorized Google OAuth redirect URIs.
5. **Welcome / Claim Campaign**: Trigger password reset emails for migrated users so they can activate their accounts on Django.
6. **Grace Period**: Allow parallel login or automatic redirect from legacy Supabase sessions during cutover window.
