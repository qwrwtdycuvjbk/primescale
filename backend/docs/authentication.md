# People Remotely — Django Authentication Architecture (Phase 3A)

## 1. Overview & Architectural Context

This document outlines the authentication, authorization, and token management foundation implemented in the Django REST Framework (DRF) backend for People Remotely.

```
========================================================================================================================
CURRENT ARCHITECTURE (ACTIVE IN PRODUCTION)          TARGET ARCHITECTURE (BEING DEVELOPED IN PARALLEL)
========================================================================================================================
Browser                                              Browser
   ↓                                                    ↓
Next.js 16 (Port 3000)                                Next.js 16 (Port 3000)
   ↓                                                    ↓ (Authorization: Bearer <JWT>)
Supabase Auth (GoTrue + Cookies)                      Django REST Framework (Port 8000)
   ↓                                                    ↓
Supabase auth.users + public.profiles                 Django accounts.User (PostgreSQL profiles table)
========================================================================================================================
```

> [!IMPORTANT]
> The existing Next.js frontend and Supabase authentication system remain 100% active and untouched. The Django authentication foundation operates independently in development and will be integrated during later cutover phases.

---

## 2. Django User Architecture

The custom user model is implemented in `accounts.User` (`backend/accounts/models.py`), mapped directly to the existing database table `profiles`:

- **Inheritance**: `AbstractBaseUser`, `PermissionsMixin`
- **Primary Key**: `id` (`UUIDField`, `default=uuid.uuid4`, `editable=False`)
- **Username Field**: `email` (`EmailField`, `unique=True`, `max_length=255`)
- **Required Fields**: `[]` (Email is the sole identifier)
- **Account Fields**:
  - `full_name` (`CharField`, `max_length=255`, blank=True)
  - `phone` (`CharField`, `max_length=50`, blank=True, null=True)
  - `role` (`CharField`, `choices=Role.choices`, default=`candidate`)
  - `is_active` (`BooleanField`, default=`True`)
  - `is_staff` (`BooleanField`, default=`False`)
  - `created_at` (`DateTimeField`, auto_now_add=True)
  - `updated_at` (`DateTimeField`, auto_now=True)

### Custom `UserManager`
- `create_user(email, password=None, **extra_fields)`: Normalizes email domain to lowercase, hashes password via Django's password hasher (or sets unusable password if None), assigns default role (`candidate`).
- `create_superuser(email, password=None, **extra_fields)`: Enforces `is_staff=True`, `is_superuser=True`, and sets `role="admin"`.

---

## 3. Role Model & Authorization

The system strictly enforces three domain roles via `User.Role`:
1. `candidate`: Job seeker creating candidate profile and reviewing matches.
2. `employer`: Company representative posting jobs and reviewing candidate shortlists.
3. `admin`: People Prime recruiter/staff member managing queues, approvals, and candidate imports.

### DRF Permission Classes (`backend/accounts/permissions.py`)
- **`IsCandidate`**: Grants access only if `request.user.is_authenticated` and `request.user.role == 'candidate'`.
- **`IsEmployer`**: Grants access only if `request.user.is_authenticated` and `request.user.role == 'employer'`.
- **`IsAdmin`**: Grants access if `request.user.role == 'admin'`, `request.user.is_staff`, or `request.user.is_superuser`.
- **`IsCandidateOrAdmin`**: Grants access to candidates or admin users.
- **`IsEmployerOrAdmin`**: Grants access to employers or admin users.
- **`IsOwnerOrAdmin`**: Reusable object-level permission checking ownership against `obj.owner`, `obj.user`, `obj.posted_by`, or `obj` (for User self-edits).

---

## 4. JWT Architecture & Token Blacklisting

Authentication is powered by `djangorestframework-simplejwt` with cryptographic HS256 signatures:

- **Access Token Lifetime**: 60 minutes (`JWT_ACCESS_TOKEN_LIFETIME_MINUTES`)
- **Refresh Token Lifetime**: 7 days (`JWT_REFRESH_TOKEN_LIFETIME_DAYS`)
- **Token Rotation**: `ROTATE_REFRESH_TOKENS = True` (a new refresh token is issued whenever refreshed)
- **Token Blacklisting**: `BLACKLIST_AFTER_ROTATION = True` (using `rest_framework_simplejwt.token_blacklist`)
- **Header Format**: `Authorization: Bearer <access_token>`

---

## 5. API Endpoint Specifications

All authentication endpoints are versioned under `/api/v1/auth/`.

### 1. User Registration (`POST /api/v1/auth/register/`)
Public registration endpoint for new candidates and employers.

- **Permissions**: `AllowAny`
- **Request Body**:
  ```json
  {
    "email": "candidate@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe",
    "phone": "+1-555-0199",
    "role": "candidate"
  }
  ```
- **Validation**:
  - `role`: Must be `"candidate"` or `"employer"`. Rejects `"admin"` with HTTP 400.
  - `email`: Normalized and verified unique.
  - `password`: Validated against Django password validation rules.
- **Response (201 Created)**:
  ```json
  {
    "access": "<JWT_ACCESS_TOKEN>",
    "refresh": "<JWT_REFRESH_TOKEN>",
    "user": {
      "id": "c1f7a24e-b5f6-4d1a-8c9f-3e2a1b4c5d6e",
      "email": "candidate@example.com",
      "full_name": "Jane Doe",
      "phone": "+1-555-0199",
      "role": "candidate",
      "created_at": "2026-09-01T12:00:00Z",
      "updated_at": "2026-09-01T12:00:00Z"
    }
  }
  ```

### 2. User Login (`POST /api/v1/auth/login/`)
Authenticates existing users via email and password.

- **Permissions**: `AllowAny`
- **Request Body**:
  ```json
  {
    "email": "candidate@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access": "<JWT_ACCESS_TOKEN>",
    "refresh": "<JWT_REFRESH_TOKEN>",
    "user": {
      "id": "c1f7a24e-b5f6-4d1a-8c9f-3e2a1b4c5d6e",
      "email": "candidate@example.com",
      "full_name": "Jane Doe",
      "phone": "+1-555-0199",
      "role": "candidate",
      "created_at": "2026-09-01T12:00:00Z",
      "updated_at": "2026-09-01T12:00:00Z"
    }
  }
  ```
- **Error Response (401 Unauthorized)**:
  ```json
  {
    "error": "Invalid email or password."
  }
  ```

### 3. Current User (`GET /api/v1/auth/me/`)
Returns authenticated user profile details.

- **Permissions**: `IsAuthenticated`
- **Header**: `Authorization: Bearer <access_token>`
- **Response (200 OK)**:
  ```json
  {
    "id": "c1f7a24e-b5f6-4d1a-8c9f-3e2a1b4c5d6e",
    "email": "candidate@example.com",
    "full_name": "Jane Doe",
    "phone": "+1-555-0199",
    "role": "candidate",
    "created_at": "2026-09-01T12:00:00Z",
    "updated_at": "2026-09-01T12:00:00Z"
  }
  ```

### 4. Token Refresh (`POST /api/v1/auth/refresh/`)
Generates a new short-lived access token using a valid refresh token.

- **Permissions**: `AllowAny`
- **Request Body**:
  ```json
  {
    "refresh": "<JWT_REFRESH_TOKEN>"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access": "<NEW_JWT_ACCESS_TOKEN>",
    "refresh": "<ROTATED_JWT_REFRESH_TOKEN>"
  }
  ```

### 5. Logout (`POST /api/v1/auth/logout/`)
Revokes a refresh token by recording it in the token blacklist table.

- **Permissions**: `AllowAny` / `IsAuthenticated`
- **Request Body**:
  ```json
  {
    "refresh": "<JWT_REFRESH_TOKEN>"
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "status": "ok",
    "message": "Successfully logged out."
  }
  ```

---

## 6. Admin Security & Lockdown

- **Self-Registration Prevention**: Public registration strictly validates `role in ('candidate', 'employer')`. Any attempt to pass `role: 'admin'` is rejected with HTTP 400 Bad Request.
- **Admin Account Creation**: Admin accounts can only be provisioned through Django CLI (`createsuperuser`) or by an existing superuser in the Django Admin interface (`/admin/`).
- **Permissions Flag Alignment**: An admin user has `role = 'admin'`, `is_staff = True`, and `is_superuser = True`. The `IsAdmin` permission accepts either `role == 'admin'` or standard Django staff/superuser privileges.

---

## 7. Password Hashing & Security

- Uses standard Django PBKDF2 with SHA-256 (`django.contrib.auth.hashers.PBKDF2PasswordHasher`) with 870,000 iterations (default for Django 5.2).
- Plaintext passwords are never stored, returned in serializers, or logged in server output.
- Password complexity is enforced via Django's `AUTH_PASSWORD_VALIDATORS` (UserAttributeSimilarityValidator, MinimumLengthValidator, CommonPasswordValidator, NumericPasswordValidator).

---

## 8. UUID Strategy & Preservability

- All User records use RFC 4122 UUID v4 primary keys (`id = models.UUIDField(primary_key=True)`).
- During production data migration, existing Supabase `auth.users.id` values can be directly copied into `accounts.User.id`, preserving all downstream foreign keys across `candidate_profiles`, `companies`, `company_members`, and `jobs`.

---

## 9. CORS & Frontend Connectivity

- **Origins Allowed**: `http://localhost:3000` (`CORS_ALLOWED_ORIGINS` via `.env`)
- **Disallowed**: `CORS_ALLOW_ALL_ORIGINS = False`
- Enables secure cross-origin requests from the Next.js development server to the Django API.

---

## 10. CSRF & Token Storage Recommendation (Next.js App Router)

### Comparison of JWT Storage Strategies:
1. **`localStorage` / `sessionStorage`**:
   - *Pros*: Simple to implement in pure client SPAs.
   - *Cons*: Vulnerable to Cross-Site Scripting (XSS). Cannot be read by Next.js Server Components or `middleware.ts`.
2. **HttpOnly Cookies**:
   - *Pros*: Immune to JavaScript-based XSS attacks. Automatically attached to all HTTP requests. Accessible in Next.js Server Actions and `middleware.ts`.
   - *Cons*: Requires CSRF protection on mutation endpoints.
3. **Next.js Server-Side Token Handling (Recommended)**:
   - Next.js Route Handlers / Server Actions manage the Django JWT in secure, `HttpOnly`, `SameSite=Lax`, `Secure` cookies.
   - Server Components and Server Actions forward the JWT in the `Authorization: Bearer <token>` header to Django REST Framework.
   - Best-in-class security matching modern App Router standards.

---

## 11. Future Migration Roadmaps

### A. Supabase User Migration (Phase 3B / Data Phase)
- Extract records from `auth.users` and `public.profiles`.
- Insert into `accounts.User` maintaining exact UUIDs.
- Existing Google OAuth users will match seamlessly by email.
- Existing email/password users will be prompted for 1-click password setup.

### B. Google OAuth Migration (Phase 3B)
- Implement Django Google OAuth token exchange endpoint (`/api/v1/auth/google/`).
- Google ID token is verified server-side, matching or provisioning `accounts.User` by verified email.

### C. Password Reset Flow (Phase 3B)
- `POST /api/v1/auth/password-reset/` $\rightarrow$ Generates `TimestampSigner` reset token $\rightarrow$ Celery task dispatches transactional email via Resend $\rightarrow$ Next.js reset page calls `POST /api/v1/auth/password-reset-confirm/`.

### D. Email Verification Flow (Phase 3B)
- Candidate registration dispatches Celery task $\rightarrow$ Resend delivers verification email $\rightarrow$ Next.js confirmation page confirms account via Django API.
