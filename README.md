# PrimeScale

AI hiring platform for **US remote tech roles**, built by [People Prime Worldwide](https://people-prime.com).

Employers post roles for free and receive recruiter-vetted candidate matches. Candidates build one profile and get matched to roles that fit their skills and work authorization. People Prime handles staffing backstop — payroll, compliance, and onboarding for contract and C2H hires.

**Live site:** [primescale.app](https://primescale.app)

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Framework | [Next.js 16](https://nextjs.org) (App Router) |
| UI | React 19, Tailwind CSS 4 |
| Database & Auth | [Supabase](https://supabase.com) (Postgres + Auth + Storage) |
| Email | [Resend](https://resend.com) |
| AI matching | OpenAI API (optional — skill scoring works without it) |
| Hosting | [Vercel](https://vercel.com) |

---

## Prerequisites

- **Node.js** 20+
- **npm** 10+
- A **Supabase** project (free tier is fine for dev)
- **Resend** API key (for ops/recruiter email notifications)
- **OpenAI** API key (optional — improves match reasons and JD parsing)

---

## Local setup

### 1. Clone and install

```bash
git clone https://github.com/qwrwtdycuvjbk/primescale.git
cd primescale
npm install
```

### 2. Environment variables

Create `.env.local` in the project root:

```bash
# Supabase (required)
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# App URLs
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_SITE_URL=http://localhost:3000

# Admin access (comma-separated emails)
ADMIN_EMAILS=you@company.com

# Email notifications (required for recruiter alerts)
RESEND_API_KEY=re_xxxxxxxx
RESEND_FROM_EMAIL=PrimeScale <onboarding@resend.dev>
PEOPLE_PRIME_HANDOFF_EMAIL=remote@people-prime.com

# Dev only — Resend sandbox redirects ops email here
RESEND_DEV_TO=you@company.com

# AI features (optional)
OPENAI_API_KEY=sk-xxxxxxxx
```

Never commit `.env.local` — it is gitignored.

### 3. Supabase database

Run these SQL files **in order** in the Supabase SQL Editor:

1. `supabase/marketplace-schema.sql` — core tables (profiles, companies, jobs, matches)
2. `supabase/employer-module.sql` — employer company fields
3. `supabase/candidate-profile-v2.sql` — extended candidate profile + resume storage
4. `supabase/auth-phone.sql` — phone auth helpers
5. `supabase/auth-profile-insert.sql` — profile creation on signup
6. `supabase/auth-oauth-fix.sql` — OAuth callback fixes
7. `supabase/handoff-queue.sql` — mutual-fit handoff queue
8. `supabase/match-review.sql` — recruiter review gate for matches
9. `supabase/profiles-rls-fix.sql` — fixes admin RLS recursion

Also enable **Email** and **Google** auth providers in Supabase → Authentication → Providers.

Set your OAuth redirect URL to:

```
http://localhost:3000/auth/callback
```

(Use your production URL in production.)

### 4. Run the dev server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Production build |
| `npm run start` | Run production build locally |
| `npm run lint` | ESLint |

---

## Project structure

```
src/
├── app/                    # Next.js App Router pages & API routes
│   ├── api/                # REST API (jobs, matches, auth, profiles)
│   ├── auth/               # Login, signup, OAuth callback, redirect
│   ├── employer/         # Employer dashboard, jobs, matches
│   ├── candidate/          # Candidate dashboard, profile, matches
│   └── admin/              # Recruiter match review & handoff queue
├── components/
│   ├── site/               # Marketing homepage components
│   ├── auth/               # Auth forms and shells
│   ├── employer/           # Job posting, match cards
│   ├── candidate/          # Profile wizard and edit forms
│   └── admin/              # Admin review UI
└── lib/                    # Business logic
    ├── matching.ts         # Skill overlap + LLM match scoring
    ├── match-runner.ts     # Runs matching on job/candidate events
    ├── job-notifications.ts
    ├── recruiter-alert.ts  # High-confidence match email alerts
    ├── handoff.ts          # Mutual-fit handoff workflow
    ├── ops-email.ts        # Resend email delivery
    └── supabase/           # Supabase client helpers

supabase/                   # SQL migrations (run manually in Supabase)
marketing/                  # Sales sheet and outreach templates
public/                     # Static assets
```

---

## How it works

### Employers

1. Sign up → complete company profile
2. Post a US remote tech role (draft or publish)
3. AI matching runs on publish; high-confidence matches alert recruiters
4. Recruiters approve matches in `/admin/matches`
5. Employers see approved matches in `/employer/matches` and can shortlist

### Candidates

1. Sign up → complete profile wizard (skills, work auth, resume)
2. Matching runs when profile is complete
3. View suggested roles in `/candidate/matches`
4. Express interest; mutual fit triggers a handoff to People Prime

### Admins (People Prime recruiters)

- `/admin/matches` — review and release matches to employers
- `/admin/handoffs` — manage mutual-fit introductions

Admin access is granted via the `ADMIN_EMAILS` env var.

---

## API routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/jobs` | POST | Create a job (draft or published) |
| `/api/jobs/[id]` | PATCH | Update job status (e.g. publish, close) |
| `/api/jobs/parse` | POST | AI-assisted JD parsing |
| `/api/candidate/profile` | POST | Create/update candidate profile |
| `/api/candidate/resume` | POST | Upload resume to Supabase Storage |
| `/api/matches` | PATCH | Update match status (interest, shortlist) |
| `/api/employer/company` | POST | Create/update company profile |
| `/api/auth/login` | POST | Email/password login |
| `/api/admin/matches/[id]` | PATCH | Approve/reject match for employer view |
| `/api/admin/handoffs/[id]` | PATCH | Update handoff queue item |

---

## Deployment

### Vercel (recommended)

1. Connect the GitHub repo to [Vercel](https://vercel.com)
2. Add all environment variables from `.env.local` in Vercel → Settings → Environment Variables
3. Set production URLs:
   - `NEXT_PUBLIC_APP_URL=https://primescale.app`
   - `NEXT_PUBLIC_SITE_URL=https://primescale.app`
4. Add `https://primescale.app/auth/callback` to Supabase OAuth redirect URLs
5. Push to `main` — Vercel deploys automatically

PR branches get preview deploy URLs for testing before merge.

---

## Contributing

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make changes and test locally
3. Open a pull request into `main`
4. Do not push directly to `main` or commit secrets

Share `.env.local` values with new developers through a password manager — never through GitHub.

---

## Marketing

Outbound templates and a sales one-pager live in `marketing/`:

- `marketing/sales-sheet.md` — employer pitch, objection handling, email templates
- `marketing/templates.md` — LinkedIn and cold email copy

---

## Contact

**People Prime Worldwide**

- Email: [remote@people-prime.com](mailto:remote@people-prime.com)
- Phone: +1 (747) 212-1886
- Web: [people-prime.com](https://people-prime.com)

---

## License

Private — © People Prime Worldwide. All rights reserved.
