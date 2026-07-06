-- Mutual-fit handoff queue for People Prime recruiters
-- Run in Supabase SQL Editor after marketplace schema

-- Allow mutual_fit on matches
alter table public.matches drop constraint if exists matches_status_check;
alter table public.matches add constraint matches_status_check check (
  status in (
    'suggested',
    'candidate_interested',
    'employer_shortlisted',
    'mutual_fit',
    'rejected'
  )
);

create table if not exists public.handoff_requests (
  id uuid primary key default gen_random_uuid(),
  match_id uuid not null unique references public.matches(id) on delete cascade,
  status text not null default 'pending' check (
    status in ('pending', 'contacted', 'intro_made', 'closed')
  ),
  notes text,
  notified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists handoff_requests_status_idx on public.handoff_requests(status);
create index if not exists handoff_requests_created_idx on public.handoff_requests(created_at desc);

alter table public.handoff_requests enable row level security;

-- Admins manage the handoff queue
create policy "handoffs_admin_select" on public.handoff_requests
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

create policy "handoffs_admin_update" on public.handoff_requests
  for update using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

-- Admins can read matches for the ops queue
create policy "matches_select_admin" on public.matches
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

-- Admins can read related records for handoff context
create policy "jobs_select_admin" on public.jobs
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

create policy "companies_select_admin" on public.companies
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

create policy "candidate_profiles_select_admin" on public.candidate_profiles
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );

create policy "profiles_select_admin" on public.profiles
  for select using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );
