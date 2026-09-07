# People Remotely — Core Domain Business APIs (Phase 4)

## 1. Overview & Architecture

This document specifies the REST APIs for **Companies**, **Company Members**, **Candidate Profiles**, and **Jobs** in Django REST Framework. These endpoints replicate the exact business rules, validations, calculations, and Row-Level Security (RLS) policies from the original Next.js/Supabase application.

```
========================================================================================================================
CURRENT ARCHITECTURE (ACTIVE IN PRODUCTION)          TARGET ARCHITECTURE (BEING DEVELOPED IN PARALLEL)
========================================================================================================================
Next.js 16 (Port 3000)                                Next.js 16 (Port 3000)
   ↓                                                    ↓ (Authorization: Bearer <JWT>)
Supabase PostgreSQL Tables                            Django REST Framework (Port 8000)
- companies                                           - /api/v1/companies/
- company_members                                     - /api/v1/candidates/
- candidate_profiles                                  - /api/v1/jobs/
- jobs                                                ↓
                                                      PostgreSQL Database
========================================================================================================================
```

---

## 2. Authorization & Role Matrix

| Endpoint | Action | Unauthenticated / Public | Candidate | Employer | Admin / Staff |
|---|---|---|---|---|---|
| **`/api/v1/companies/me/`** | `GET` | 401 Unauthorized | 403 Forbidden | Own Company | All / Own |
| **`/api/v1/companies/me/`** | `POST` / `PATCH` | 401 Unauthorized | 403 Forbidden | Create/Update Own | Allowed |
| **`/api/v1/companies/<id>/`** | `GET` | Public Data | Public Data | Own: Full; Other: Public | Full Data |
| **`/api/v1/companies/<id>/members/`** | `GET` / `POST` | 401 Unauthorized | 403 Forbidden | Company Owner/Admin only | Allowed |
| **`/api/v1/candidates/me/`** | `GET` | 401 Unauthorized | Own Profile | 403 Forbidden | All / Own |
| **`/api/v1/candidates/me/`** | `POST` / `PATCH` | 401 Unauthorized | Create/Update Own | 403 Forbidden | Allowed |
| **`/api/v1/candidates/public-showcase/`** | `GET` | Allowed (Anonymized) | Allowed (Anonymized) | Allowed (Anonymized) | Allowed |
| **`/api/v1/candidates/<id>/`** | `GET` | 401 Unauthorized | 403 Forbidden | 403 Forbidden | Allowed |
| **`/api/v1/jobs/`** | `GET` | Active Non-expired | Active Non-expired | Own Company (`?view=my_company`) | Full Filtered Registry |
| **`/api/v1/jobs/`** | `POST` | 401 Unauthorized | 403 Forbidden | Create for Own Company | Allowed |
| **`/api/v1/jobs/<id>/`** | `GET` | Active Non-expired | Active Non-expired | Own: Full; Other: Active | Full Data |
| **`/api/v1/jobs/<id>/`** | `PATCH` / `DELETE`| 401 Unauthorized | 403 Forbidden | Poster/Owner only | Allowed |
| **`/api/v1/jobs/<id>/duplicate/`** | `POST` | 401 Unauthorized | 403 Forbidden | Poster/Owner only | Allowed |

---

## 3. Companies & Members API (`/api/v1/companies/`)

### 1. `GET /api/v1/companies/me/`
- **Auth**: Required (`employer` or `admin`)
- **Response (200 OK)**:
  ```json
  {
    "id": "18f921ea-3610-449e-b8eb-ec0fcb1ee0d0",
    "owner": "c1f7a24e-b5f6-4d1a-8c9f-3e2a1b4c5d6e",
    "owner_email": "employer@acme.com",
    "name": "Acme Corp",
    "website": "https://acme.com",
    "size": "51-200",
    "country": "US",
    "logo_url": "https://bucket/logos/logo.png",
    "description": "Leading cloud tooling company.",
    "hq_city": "San Francisco",
    "industry": "Software",
    "remote_culture_statement": "Async-first, remote-native culture.",
    "domain_verified": true,
    "badge_remote_first": true,
    "badge_visa_sponsor": false,
    "badge_gcc": false,
    "profile_complete": true,
    "members": [
      {
        "id": "75c3db73-c15b-4395-888a-2bb67341e97d",
        "company": "18f921ea-3610-449e-b8eb-ec0fcb1ee0d0",
        "user": "c1f7a24e-b5f6-4d1a-8c9f-3e2a1b4c5d6e",
        "user_email": "employer@acme.com",
        "user_full_name": "Acme Lead",
        "member_role": "admin",
        "created_at": "2026-09-02T12:00:00Z"
      }
    ],
    "created_at": "2026-09-02T12:00:00Z",
    "updated_at": "2026-09-02T12:00:00Z"
  }
  ```

### 2. `POST /api/v1/companies/me/`
- **Auth**: Required (`employer` or `admin`)
- **Request Body**:
  ```json
  {
    "name": "Acme Corp",
    "website": "https://acme.com",
    "size": "51-200",
    "description": "Leading cloud tooling company.",
    "hq_city": "San Francisco",
    "industry": "Software",
    "remote_culture_statement": "Async-first.",
    "badge_remote_first": true,
    "work_email": "recruiter@acme.com"
  }
  ```
- **Business Logic**:
  - `domain_verified`: Compares email domain with website host.
  - `profile_complete`: `bool(name && size && description && hq_city && industry)`.
  - Auto-creates `CompanyMember(member_role='admin')` on creation.
- **Response (201 Created / 200 OK)**:
  ```json
  {
    "ok": true,
    "companyId": "18f921ea-3610-449e-b8eb-ec0fcb1ee0d0",
    "domainVerified": true,
    "profileComplete": true,
    "company": { ... }
  }
  ```

### 3. `GET /api/v1/companies/<uuid:pk>/`
- **Auth**: Public (returns sanitized fields) or Owner/Admin (returns full details).

### 4. `GET / POST /api/v1/companies/<uuid:pk>/members/`
- **Auth**: Required (Owner or Admin only)
- **POST Body**:
  ```json
  {
    "email": "recruiter@acme.com",
    "member_role": "recruiter"
  }
  ```

---

## 4. Candidate Profiles API (`/api/v1/candidates/`)

### 1. `GET /api/v1/candidates/me/`
- **Auth**: Required (`candidate` or `admin`)
- **Response (200 OK)**: Returns full candidate profile.

### 2. `POST /api/v1/candidates/me/`
- **Auth**: Required (`candidate` or `admin`)
- **Request Body**:
  ```json
  {
    "headline": "Lead Python & Distributed Systems Engineer",
    "phone": "+1-555-0199",
    "current_title": "Staff Engineer",
    "years_experience": 8,
    "skills": "Python, Django, PostgreSQL, Redis, Celery, AWS",
    "role_categories": ["Backend", "DevOps"],
    "experience_level": "senior",
    "salary_min": 150000,
    "salary_max": 190000,
    "work_authorization": "us_citizen",
    "us_state": "California",
    "remote_preference": "remote",
    "preferred_work_type": "remote",
    "resume_url": "https://bucket/resumes/resume.pdf",
    "github_url": "https://github.com/alice",
    "portfolio_url": "https://alice.dev",
    "linkedin_url": "https://linkedin.com/in/alice",
    "bio": "Specialized in microservices architecture and high-throughput systems.",
    "availability_status": "actively_looking",
    "privacy_visibility": "public"
  }
  ```
- **Business Logic & Completeness Algorithm**:
  - Automatically runs the **15-check completeness calculation** (headline, phone, current_title, years_experience, skills, role_categories, experience_level, work_authorization, us_state, salary, bio, resume_url, links, availability_status, preferred_work_type).
  - Automatically verifies `profile_complete = (required_fields && resume_url)`.
  - Automatically sets `open_to_matching = (availability_status != 'not_looking')`.
  - Synchronizes phone number to `request.user.phone`.
- **Response (200 OK)**:
  ```json
  {
    "ok": true,
    "candidateProfileId": "099a4c84-8848-4366-a367-932d2ea8a562",
    "profileCompleteness": 100,
    "profileComplete": true,
    "profile": { ... }
  }
  ```

### 3. `GET /api/v1/candidates/public-showcase/`
- **Auth**: Public (`AllowAny`)
- **Filtering**: `privacy_visibility='public'`, `profile_complete=True`, `open_to_matching=True`, `availability_status__in=['actively_looking', 'open']`.
- **Response (200 OK)**: Returns list of anonymized talent cards (`displayName`: "Alice C.", `initials`: "AC", top 3 skills, `hiddenSkillCount`: N, `salaryRange`: "$150k–$190k").

---

## 5. Jobs API (`/api/v1/jobs/`)

### 1. `GET /api/v1/jobs/`
- **Auth**: Public / Candidate / Employer / Admin
- **Parameters**:
  - `status`: Filter by status (`active`, `draft`, `paused`, `closed`, `archived`) — admin only or company jobs.
  - `experience_level` / `experience`: (`junior`, `mid`, `senior`, `lead`).
  - `role_type`: (`full-time`, `contract`, `c2h`).
  - `work_type`: (`remote`, `hybrid`, `onsite`).
  - `q`: Search query matched across title, description, and company name.
  - `view=my_company`: Employer views their own posted jobs.

### 2. `POST /api/v1/jobs/`
- **Auth**: Required (`employer` or `admin`)
- **Request Body**:
  ```json
  {
    "title": "Senior Backend Engineer",
    "description": "Designing high-scale APIs in Django & Celery.",
    "role_type": "full-time",
    "experience_level": "senior",
    "tech_stack": ["Python", "Django", "PostgreSQL", "Redis"],
    "salary_range": "$140,000 - $175,000",
    "work_type": "remote",
    "visa_requirements": "US Authorized only",
    "publish": true
  }
  ```
- **Validation Rules**:
  - `salary_range`: Rejects blocked phrases ("Competitive", "DOE", "Negotiable", "TBD"). Must contain numbers and have length >= 3.
  - `tech_stack`: Must contain at least 3 skills.
  - `publish`: If `True`, sets `status = 'active'` and `expires_at = now + 30 days`. If `False`, sets `status = 'draft'`.
- **Response (201 Created)**:
  ```json
  {
    "ok": true,
    "jobId": "4a761e06-cbf7-48f8-a006-25f1906a2ff2",
    "status": "active",
    "job": { ... }
  }
  ```

### 3. `PATCH /api/v1/jobs/<uuid:pk>/`
- **Auth**: Required (Job poster, Company Owner, or Admin)
- **Behavior**: Updates job details. If status transitions to `active`, auto-renews `expires_at` to +30 days.

### 4. `POST /api/v1/jobs/<uuid:pk>/duplicate/`
- **Auth**: Required (Job poster, Company Owner, or Admin)
- **Behavior**: Clones job as `draft` with `${source.title} (copy)`. Returns 201 with `jobId`.

---

## 6. Verification & Test Summary

- All 54 tests passing (`python manage.py test`):
  - 34 Authentication, Authorization & User Model tests
  - 7 Company & Member tests
  - 6 Candidate Profile & Completeness tests
  - 7 Job creation, filtering, validation & duplication tests
- Zero Next.js frontend or Supabase files modified.
