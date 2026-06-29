-- PrimeScale marketplace schema (run in Supabase SQL Editor after enabling Auth)
-- US tech roles only; employers post jobs, candidates get matched via profile

-- Profiles (one per auth user)
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  role text not null check (role in ('employer', 'candidate', 'admin')),
  full_name text not null default '',
  email text not null,
  phone text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Employer companies
create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  website text,
  size text,
  country text not null default 'US',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists companies_owner_id_idx on public.companies(owner_id);

-- Candidate profiles (match-ready)
create table if not exists public.candidate_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.profiles(id) on delete cascade,
  headline text,
  skills text[] not null default '{}',
  role_categories text[] not null default '{}',
  experience_level text,
  salary_min integer,
  salary_max integer,
  work_authorization text,
  us_state text,
  remote_preference text not null default 'remote',
  resume_url text,
  bio text,
  open_to_matching boolean not null default true,
  profile_complete boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Employer job posts
create table if not exists public.jobs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  posted_by uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  description text not null,
  role_type text not null,
  experience_level text not null,
  tech_stack text[] not null default '{}',
  salary_range text,
  work_type text not null default 'remote',
  visa_requirements text,
  status text not null default 'active' check (status in ('draft', 'active', 'closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- AI / skill-based matches
create table if not exists public.matches (
  id uuid primary key default gen_random_uuid(),
  candidate_profile_id uuid not null references public.candidate_profiles(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete cascade,
  match_score integer not null default 0 check (match_score >= 0 and match_score <= 100),
  match_reason text,
  status text not null default 'suggested' check (
    status in ('suggested', 'candidate_interested', 'employer_shortlisted', 'rejected')
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (candidate_profile_id, job_id)
);

create index if not exists matches_candidate_idx on public.matches(candidate_profile_id);
create index if not exists matches_job_idx on public.matches(job_id);
create index if not exists jobs_status_idx on public.jobs(status);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role, full_name, email)
  values (
    new.id,
    coalesce(nullif(new.raw_user_meta_data->>'role', ''), 'candidate'),
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    coalesce(new.email, '')
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- RLS
alter table public.profiles enable row level security;
alter table public.companies enable row level security;
alter table public.candidate_profiles enable row level security;
alter table public.jobs enable row level security;
alter table public.matches enable row level security;

-- Profiles: users read/update own row
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);

create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id);

-- Companies: owner CRUD
create policy "companies_select_own" on public.companies
  for select using (auth.uid() = owner_id);

create policy "companies_insert_own" on public.companies
  for insert with check (auth.uid() = owner_id);

create policy "companies_update_own" on public.companies
  for update using (auth.uid() = owner_id);

-- Candidate profiles: owner CRUD
create policy "candidate_profiles_select_own" on public.candidate_profiles
  for select using (auth.uid() = user_id);

create policy "candidate_profiles_insert_own" on public.candidate_profiles
  for insert with check (auth.uid() = user_id);

create policy "candidate_profiles_update_own" on public.candidate_profiles
  for update using (auth.uid() = user_id);

-- Jobs: employers manage own; candidates read active jobs
create policy "jobs_select_active" on public.jobs
  for select using (
    status = 'active'
    or posted_by = auth.uid()
  );

create policy "jobs_insert_own" on public.jobs
  for insert with check (auth.uid() = posted_by);

create policy "jobs_update_own" on public.jobs
  for update using (auth.uid() = posted_by);

-- Matches: candidates see theirs; employers see matches on their jobs
create policy "matches_select_candidate" on public.matches
  for select using (
    exists (
      select 1 from public.candidate_profiles cp
      where cp.id = candidate_profile_id and cp.user_id = auth.uid()
    )
    or exists (
      select 1 from public.jobs j
      where j.id = job_id and j.posted_by = auth.uid()
    )
  );

create policy "matches_update_candidate" on public.matches
  for update using (
    exists (
      select 1 from public.candidate_profiles cp
      where cp.id = candidate_profile_id and cp.user_id = auth.uid()
    )
    or exists (
      select 1 from public.jobs j
      where j.id = job_id and j.posted_by = auth.uid()
    )
  );

-- Service role inserts matches via API (bypasses RLS with service key)
