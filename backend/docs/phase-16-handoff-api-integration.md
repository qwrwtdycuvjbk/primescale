# Phase 16 — Handoff Requests API Integration

## 1. Overview & Architecture

Phase 16 migrates the **Handoff Requests** module from Supabase to Django REST Framework (`backend/handoffs/`) backed by local PostgreSQL (`peopleremotely_local`), with temporary Supabase fallback preserved for non-breaking backward compatibility.

When candidates and employers reach a **mutual fit** (both candidate and employer express mutual interest), the deterministic matching workflow automatically provisions a `HandoffRequest` record for recruiter action.

```
Next.js UI (Admin Handoff Queue / Dashboard)
           │
           ▼
Next.js API Client layer (`src/lib/api/handoffs.ts`)
           │  (Django-First with automatic Supabase fallback)
           ▼
Next.js Route Handlers (`src/app/api/admin/handoffs/[id]/route.ts`)
           │  (Bearer token forwarding)
           ▼
Django REST API (`/api/v1/handoffs/`)
           │  (Strict role-based permissions & IDOR isolation)
           ▼
Local PostgreSQL (`peopleremotely_local`)
```

---

## 2. Data Models & Relationships

### `HandoffRequest` (`backend/handoffs/models.py`)
Each handoff request is tied to a single `Match` record through a `OneToOneField`, preventing duplicate handoff requests for the same match.

```python
class HandoffRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONTACTED = "contacted"
    STATUS_INTRO_MADE = "intro_made"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONTACTED, "Contacted"),
        (STATUS_INTRO_MADE, "Introduction Made"),
        (STATUS_CLOSED, "Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name="handoff_request",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True, null=True)
    notified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## 3. Endpoints & REST Conventions

All endpoints are mounted under `/api/v1/handoffs/` with JWT authentication (`IsAuthenticated`).

| Method | Endpoint | Allowed Roles | Description |
|---|---|---|---|
| `GET` | `/api/v1/handoffs/` | Admin, Candidate, Employer | Lists handoffs. Admins see all (filterable by `?status=`). Candidates only see handoffs linked to their candidate profile. Employers only see handoffs linked to their posted jobs or owned company. |
| `GET` | `/api/v1/handoffs/<uuid:pk>/` | Admin, Candidate, Employer | Retrieves a single handoff with full match, candidate profile, and employer information. Strict IDOR protection rejects unauthorized viewers with `403 Forbidden`. |
| `POST` | `/api/v1/handoffs/` | Admin | Explicit handoff creation. Validates match existence and enforces single handoff constraint per match (`400 Bad Request` if duplicate). |
| `PATCH` | `/api/v1/handoffs/<uuid:pk>/` | Admin | Updates status (`pending`, `contacted`, `intro_made`, `closed`) and recruiter `notes`. Candidates and employers attempting to patch receive `403 Forbidden`. Invalid statuses receive `400 Bad Request`. |

---

## 4. Permissions & Security / IDOR Protection

1. **Candidate Security**:
   - Filter query: `match__candidate_profile__user = request.user`.
   - Cannot view handoffs for other candidates or companies.
   - Prohibited from updating recruiter notes or statuses (`HTTP 403`).
2. **Employer Security**:
   - Filter query: `match__job__posted_by = request.user` or `match__job__company__owner = request.user`.
   - Cannot view handoffs for other companies.
   - Prohibited from updating recruiter notes or statuses (`HTTP 403`).
3. **Admin Security**:
   - Unrestricted access to view and update recruiter notes and statuses.
4. **Duplicate Prevention**:
   - Database level `OneToOneField(Match)` enforces uniqueness.
   - Serializer explicitly checks `HandoffRequest.objects.filter(match=match).exists()`.

---

## 5. Serializer & UI Compatibility

`HandoffRequestSerializer` produces nested structures identical to what the existing Next.js `HandoffCard` component expects:

```json
{
  "id": "c6ff8827-0c15-46aa-83a3-dcfd9f6ea14b",
  "match_id": "c1f7da4d-82d2-436f-b27e-ae18e76fb211",
  "status": "pending",
  "notes": "Candidate prefers Slack intro.",
  "notified_at": "2026-09-08T15:25:00Z",
  "created_at": "2026-09-08T15:25:00Z",
  "updated_at": "2026-09-08T15:25:00Z",
  "match": {
    "id": "c1f7da4d-82d2-436f-b27e-ae18e76fb211",
    "match_score": 100,
    "status": "mutual_fit",
    "job": {
      "id": "...",
      "title": "Senior Python Backend Engineer",
      "company_name": "Acme Labs",
      "companies": { "name": "Acme Labs", "logo_url": null }
    },
    "jobs": { "title": "Senior Python Backend Engineer", ... },
    "candidate_profile": {
      "id": "...",
      "headline": "Lead Python Engineer",
      "profiles": { "full_name": "Jane Doe", "email": "jane@example.com" },
      "user": { "full_name": "Jane Doe", "email": "jane@example.com", "phone": "+1 555-0199" }
    },
    "candidate_profiles": {
      "headline": "Lead Python Engineer",
      "profiles": { "full_name": "Jane Doe", "email": "jane@example.com" }
    }
  },
  "matches": { ... },
  "employer": {
    "id": "...",
    "full_name": "John Recruiter",
    "email": "recruiter@acme.com",
    "phone": "+1 555-0100"
  }
}
```

---

## 6. Frontend Migration & Supabase Fallback

- **API Client** (`src/lib/api/handoffs.ts`):
  Centralized client exporting `handoffsApi.listHandoffs()`, `handoffsApi.getHandoff()`, and `handoffsApi.updateHandoff()`.
- **Admin Handoffs Page** (`src/app/admin/handoffs/page.tsx`):
  Fetches from `handoffsApi.listHandoffs()` with automatic fallback to Supabase `supabase.from("handoff_requests")`.
- **Admin Dashboard Counts** (`src/lib/admin-dashboard.ts`):
  `loadAdminNavCounts` queries `handoffsApi.listHandoffs("pending")` to populate badge indicators, with Supabase fallback on error.
- **Route Handler** (`src/app/api/admin/handoffs/[id]/route.ts`):
  Receives frontend PATCH requests, resolves session cookies, and forwards the update to Django with Bearer JWT token.

---

## 7. Verification & Test Results

### Phase 16 Handoff Integration Tests (`scripts/test-phase16-handoffs.mjs`)
- **38/38 PASSED (100%)**
  - Registration of Candidates 1 & 2 and Employers 1 & 2
  - Matching pipeline trigger to `mutual_fit` $\to$ automatic handoff generation
  - Admin queue listing, status filtering, and detail extraction
  - Nested candidate and employer contact detail resolution
  - Recruiter status transition (`pending` $\to$ `contacted` $\to$ `intro_made`) and notes editing
  - Candidate 1 sees only own handoff; Candidate 2 receives `403 Forbidden` / 0 queue items
  - Employer 1 sees only own handoff; Employer 2 receives `403 Forbidden` / 0 queue items
  - Non-admins prohibited from modifying status/notes (`403 Forbidden`)
  - Duplicate handoff rejection (OneToOne match uniqueness)
  - Invalid status rejection (`400 Bad Request`)

### Regression Verification
- **Django Unit & Model Tests**: **99/99 PASSED**
- **Phase 12 Auth Integration**: **16/16 PASSED**
- **Phase 13 Companies & Candidates Integration**: **29/29 PASSED**
- **Phase 14 Jobs Integration**: **31/31 PASSED**
- **Phase 15 Matches Integration**: **36/36 PASSED**
- **Django System Checks (`python manage.py check`)**: **0 issues identified**
- **Next.js Production Build (`npm run build`)**: **56/56 routes compiled successfully**

---

## 8. Production Safety & Invariants

- **Supabase production records modified**: NO
- **Supabase Auth modified**: NO
- **Supabase Storage modified**: NO
- **Production deployment performed**: NO
- **Supabase fallback active**: YES (in both page views and dashboard nav count loaders)
- **AI matching touched**: NO (deterministic algorithm preserved)
