# People Remotely — Matching Engine & Recruiter Handoff Queue (Phase 5)

## 1. Overview & Architecture

This document specifies the technical architecture for the **Matching Engine**, **Match Interaction APIs**, **Mutual Fit State Machine**, **Recruiter Handoff Queue**, and **Celery Task Orchestration** in Django REST Framework.

```
========================================================================================================================
MATCH GENERATION & MUTUAL FIT FLOW
========================================================================================================================
[Job Created / Candidate Profile Complete]
    │
    ├──► Celery Task: run_matching_for_job_task / run_matching_for_candidate_task
    │       │
    │       ▼
    │   [Matching Service]
    │       - compute_skill_overlap_score (Weight: 70%)
    │       - compute_experience_score (Weight: 30%)
    │       - combined_match_score = round(skill * 0.7 + exp * 0.3)
    │       │
    │       ├── (Score < 85) ──► Ignored
    │       └── (Score >= 85) ─► Upsert Match (status: "suggested", visible_to_employer: False)
    │                               │
    │                               ▼
    │                           [Recruiter Review Queue]
    │                               │
    │                   Admin Approves (visible_to_employer = True)
    │                               │
    ▼                               ▼
[Candidate Views Match]     [Employer Views Candidate]
    │                               │
Candidate Interested           Employer Shortlists
    │                               │
    └───────────────────────┬───────┘
                            ▼
              [resolve_match_status]
                     mutual_fit
                            │
                            ▼ (Atomic Transaction)
              [create_mutual_fit_handoff]
              - Create HandoffRequest (status: "pending")
              - Recruiter Alert (Celery / Resend)
                            │
                            ▼
              [Admin Handoff Queue]
              - Status: pending -> contacted -> intro_made -> closed
========================================================================================================================
```

---

## 2. Matching Algorithm Specification

### A. Skill Overlap Score (70% Weight) `[CONFIRMED]` & `[IMPLEMENTED]`
- **Parser**: Splits input on `[,;\n|]`, lowercases, trims whitespace, and deduplicates.
- **Substring Match Rule**: A candidate skill matches a job skill if `candidate_skill == job_skill or job_skill in candidate_skill or candidate_skill in job_skill`.
- **Formula**:
  $$\text{Skill Score} = \text{round}\left(\frac{\text{Number of Matched Job Skills}}{\text{Total Job Required Skills}} \times 100\right)$$
  - *Edge Case*: If job has no skills $\rightarrow$ 40
  - *Edge Case*: If candidate has no skills $\rightarrow$ 0

### B. Experience Score (30% Weight) `[CONFIRMED]` & `[IMPLEMENTED]`
- **Hierarchy**: `["junior", "mid", "senior", "lead"]`
- **Scoring Matrix**:
  - Candidate Level $\ge$ Job Level (Diff $\ge 0$) $\rightarrow$ **100**
  - Candidate Level 1 step below Job Level (Diff $== -1$) $\rightarrow$ **70**
  - Candidate Level 2+ steps below Job Level (Diff $\le -2$) $\rightarrow$ **40**
  - Unknown or Missing Level $\rightarrow$ **50**

### C. Combined Final Match Score `[CONFIRMED]` & `[IMPLEMENTED]`
$$\text{Match Score} = \text{round}(\text{Skill Score} \times 0.7 + \text{Experience Score} \times 0.3)$$
- Range: $0 \le \text{Match Score} \le 100$
- High-confidence Threshold: $\ge 85$ (`MIN_MATCH_SCORE`)

---

## 3. Match Status State Machine & Mutual Fit

### Allowed Statuses `[CONFIRMED]`:
1. `suggested`: Initial state upon automated generation.
2. `candidate_interested`: Candidate marked interest in the role.
3. `employer_shortlisted`: Employer shortlisted the candidate.
4. `mutual_fit`: Both parties expressed interest (candidate first or employer first).
5. `rejected`: Either party or admin rejected the match.

### Transition Rules (`resolve_match_status`):
- `candidate_interested` + `employer_shortlisted` $\rightarrow$ `mutual_fit`
- `employer_shortlisted` + `candidate_interested` $\rightarrow$ `mutual_fit`
- Any `rejected` action $\rightarrow$ `rejected`
- If match is already `mutual_fit` or `rejected`, further updates are blocked with HTTP 400 ("Match is already closed").

---

## 4. Recruiter Gate & Employer Visibility

- By default, generated matches are created with `visible_to_employer = False`.
- Candidates see all high matches for their profile (`GET /api/v1/matches/`).
- Employers only see matches where `visible_to_employer = True` (`GET /api/v1/matches/`).
- **Admin Match Action Gate (`PATCH /api/v1/matches/<id>/admin-action/`)**:
  - `action: "approve"` $\rightarrow$ sets `visible_to_employer = True` (releasing candidate to employer dashboard).
  - `action: "reject"` $\rightarrow$ sets `visible_to_employer = False, status = "rejected"`.

---

## 5. Recruiter Handoff Queue (`/api/v1/handoffs/`)

- Triggered automatically within `transaction.atomic()` upon entering `mutual_fit`.
- Idempotent: `HandoffRequest.objects.get_or_create(match=match)`.
- **Status Lifecycle**:
  1. `pending`: Awaiting recruiter initial review.
  2. `contacted`: Recruiter has reached out to both parties.
  3. `intro_made`: Introduction email/Slack made between candidate and company.
  4. `closed`: Placement completed or process concluded.
- Recruiter notes can be updated via `PATCH /api/v1/handoffs/<id>/`.
- Candidate and Employer access to `/api/v1/handoffs/` is strictly forbidden (HTTP 403).

---

## 6. Celery Task Architecture & Idempotency

### Task 1: `run_matching_for_candidate_task(candidate_profile_id)`
- Dispatched when a candidate profile is marked complete.
- Iterates over active jobs and creates/updates `Match` records.
- Idempotent: uses `update_or_create` on `UNIQUE(candidate_profile, job)`.

### Task 2: `run_matching_for_job_task(job_id)`
- Dispatched when an employer publishes an active job.
- Iterates over complete & open candidates.
- Idempotent: uses `update_or_create`.

### Task 3: `notify_recruiter_task(match_id, notification_type)`
- Dispatches transactional ops notification for scores $\ge 85$ or candidate interest.
- Idempotent: verifies `recruiter_notified_at is null` before sending and records timestamp.

---

## 7. API Endpoints Summary

### Matches API (`/api/v1/matches/`)
| Method | Endpoint | Auth | Role | Purpose |
|---|---|---|---|---|
| `GET` | `/api/v1/matches/` | Bearer JWT | Candidate / Employer / Admin | List matches filtered by user role |
| `GET` | `/api/v1/matches/<id>/` | Bearer JWT | Match owner / Admin | Retrieve detailed match info |
| `PATCH` | `/api/v1/matches/<id>/` | Bearer JWT | Match owner / Admin | Update status (`candidate_interested`, `employer_shortlisted`, `rejected`) |
| `PATCH` | `/api/v1/matches/<id>/admin-action/` | Bearer JWT | Admin only | Approve (release to employer) or Reject match |

### Handoffs API (`/api/v1/handoffs/`)
| Method | Endpoint | Auth | Role | Purpose |
|---|---|---|---|---|
| `GET` | `/api/v1/handoffs/` | Bearer JWT | Admin only | List mutual-fit handoff queue (supports `?status=`) |
| `GET` | `/api/v1/handoffs/<id>/` | Bearer JWT | Admin only | Retrieve detailed handoff info |
| `PATCH` | `/api/v1/handoffs/<id>/` | Bearer JWT | Admin only | Update handoff status and recruiter notes |

---

## 8. Verification & Test Summary

- **Total Test Suite**: **69 / 69 tests passing (`OK`)**
  - Authentication & Authorization: 34 tests
  - Companies & Members: 7 tests
  - Candidate Profiles & Completeness: 6 tests
  - Jobs & Filtering: 7 tests
  - Matching Engine & State Machine: 12 tests
  - Handoff Queue & Isolation: 3 tests
