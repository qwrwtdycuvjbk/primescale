# 30-day growth tracker

Use with [growth-tracker.csv](./growth-tracker.csv) and the public board at `/matching`.

## Daily ops rhythm

- 20–30 targeted emails (HN + Apollo + LinkedIn)
- Every “yes / tell me more” → draft job in admin → promise shortlist date
- Update tracker: company, seat, stage, next_action

## Stages (use in `stage` column)

| Stage | Meaning |
|---|---|
| `sent` | Outbound sent |
| `opened` | Opened / clicked |
| `replied` | Conversation started |
| `shortlist_promised` | Date promised |
| `shortlist_delivered` | 3 profiles sent |
| `intro` | Interview scheduled |
| `trial` | 2-day trial |
| `won` / `lost` / `nurture` | Outcome |

## 30-day targets

| Metric | Target |
|---|---|
| Real roles posted or actively matching | 5–10 |
| Free shortlists delivered | 8–12 |
| Companies in reply/conversation | 15+ |
| Candidate signups (Matching + LinkedIn) | 50–100 |
| Paid / trial conversions | 1–2 |

## Weekly ritual

**Shortlist Thursday** — post the 2–3 live seats from `/matching` using the LinkedIn template in [templates.md](./templates.md).

## Seeded matching seats (edit in code)

Update titles/status in [`src/lib/matching-seats.ts`](../src/lib/matching-seats.ts) as seats move `collecting` → `shortlisting` → `trial`.
