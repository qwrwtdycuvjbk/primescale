# Public jobs for traffic (ethical / legal)

Internal product + ops doc for People Remotely.  
**Goal:** more traffic via a public remote-tech job index, without becoming an illegal scrape site or a fake ATS.

---

## Decision

| Do | Don’t |
|---|---|
| Use a **licensed jobs API** (e.g. OpenWeb Ninja / JSearch) | Scrape LinkedIn, Wellfound, or other boards against ToS |
| Show listings as a **discovery layer** | Claim every role is “ours” or that we already represent the employer |
| Attribute source + link out to apply | Dump full stolen JDs if the license forbids it |
| Offer **Get matched on People Remotely** as opt-in | Auto-apply candidates to external jobs without consent |
| Convert interested companies onto People Remotely | Fake employer accounts or invent hiring contacts |

**Positioning line:** People Remotely remains the shortlist product. The public index is how strangers find us.

---

## Option chosen: API public board (Option 1)

Nightly (or scheduled) API pull → dedupe → public `/jobs` → each card has **Apply externally** + **Get matched on People Remotely**.

### Pipeline

1. **Pull** — remote + tech only (filters: work from home, role titles, exclude staffing spam publishers where possible).
2. **Dedupe** — same company + title (and/or same apply URL) within a window.
3. **Store (minimal fields)**  
   - title  
   - company  
   - location  
   - apply link  
   - source / provider  
   - posted date  
   - external id  
   - **Not** full JD text if the API/license says no.
4. **Publish** — indexable public pages under `/jobs` (or a clear section; keep `/matching` for seats we actually shortlist).
5. **Card CTAs**  
   - **Apply on company site** → outbound apply URL  
   - **Get matched on People Remotely** → signup / profile + interest on that listing
6. **Footer / disclosure**  
   > Listings via [provider]. We don’t employ for every role shown. “Get matched” means we may reach out to the company on your behalf — it is not an auto-apply.

---

## “Get matched” → how we contact the company

API listings have **no employer account** on People Remotely. Contact is **enrichment + outbound**, then convert them onto the platform.

```
Candidate clicks “Get matched”
        ↓
Auth + profile + interest saved (company, title, apply URL, source)
        ↓
Ops finds hiring contact (Apollo / Hunter / LinkedIn / careers page)
        ↓
Outreach: “We have 1–3 fits for your [ROLE]”
        ↓
Company engages → invite to post free on People Remotely
        ↓
Normal shortlist + handoff (on-platform)
```

### Product capture

When a candidate opts in, store:

| Field | Purpose |
|---|---|
| Candidate id | Who wants the role |
| External job id / URL | Which listing |
| Company + title | Pitch copy |
| Interest status | new / outreach / replied / posted / closed |
| Contact found (name, email, LinkedIn) | Who we emailed |
| Outcome | intro / they posted / no reply |

Admin surface: **External interests** (alongside Job leads / Handoffs).

### Ops contact rules

- Find founder, eng manager, or talent — not random scraped emails.
- Open with a **shortlist offer**, not “please sign up.”
- When they engage, create/post the role on People Remotely and attach interested candidates.
- Until they post, this is People Prime–style outbound. After they post, use normal handoffs.

### Candidate-facing promise (ethical)

> We’ll match you and reach out to [Company] on your behalf. This isn’t an auto-apply. You’ll hear from us if we’re introducing you.

### Throughput gate

Do not offer unlimited “Get matched” on every listing. Cap by ops capacity (e.g. first N interests/day, or only fresh remote-tech non-agency roles). Collecting demand without outreach breaks trust.

---

## Example outreach (after candidate interest)

**Subject:** Hiring [ROLE] at [Company]? We have candidates ready

Hi [Name],

We saw [Company] is hiring a [ROLE]. A few candidates on People Remotely fit the seat and asked us to reach out.

Happy to share 2–3 profiles at no cost. If useful, you can post the role free on People Remotely so we can run intros cleanly (payroll/compliance via People Prime if you hire).

[Link to post] · [Your name]

---

## Legal / ethics checklist

- [ ] Licensed API only; no site scraping of protected boards  
- [ ] Follow provider ToS (storage, display, attribution)  
- [ ] Attribute provider on public pages  
- [ ] Outbound apply links to original source  
- [ ] Don’t claim “we’re hiring for X” unless we are  
- [ ] Candidate opt-in before company outreach  
- [ ] Don’t store/resell applicant PII against roles we don’t own  
- [ ] Keep marketing honest: API listings ≠ seats we’re shortlisting on `/matching`

---

## What stays separate

| Surface | Purpose |
|---|---|
| `/jobs` (public API index) | SEO + traffic + discovery |
| `/matching` | Seats People Remotely is actually shortlisting |
| `/admin/job-leads` | Private pull for outbound (no public dump required) |
| Employer-posted jobs | Real platform inventory + handoffs |

---

## Call / alignment one-liner

> We grow traffic with a public remote-tech job index from a licensed API, with attribution and apply-on-company-site. “Get matched” is candidate opt-in; we find the hiring contact, pitch a shortlist, and pull the company onto People Remotely. We do not scrape LinkedIn/Wellfound or pretend we already work for those employers.

---

## Build order (when ready)

1. Schema + ingest from OpenWeb Ninja (fields above + dedupe)  
2. Public `/jobs` list + detail pages (SEO titles/descriptions)  
3. Dual CTA + interest capture → admin queue + ops email  
4. Ops playbook + tracker columns for external interests  
5. Disclosure footer + marketing copy update (don’t say “not a scraped board” if `/jobs` exists — say “licensed listings + our matching seats”)

---

## Success metrics

- Organic visits to `/jobs`  
- Candidate signups from “Get matched”  
- External interests → outreach sent  
- Companies that reply / post on People Remotely  
- Shortlists delivered from those posts  

Primary product KPI is still **companies posting + shortlists delivered**, not listing count alone.
