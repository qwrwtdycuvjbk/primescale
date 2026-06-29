-- Employer module (run after marketplace-schema.sql)

alter table public.companies
  add column if not exists logo_url text,
  add column if not exists description text,
  add column if not exists hq_city text,
  add column if not exists industry text,
  add column if not exists remote_culture_statement text,
  add column if not exists domain_verified boolean not null default false,
  add column if not exists badge_remote_first boolean not null default false,
  add column if not exists badge_visa_sponsor boolean not null default false,
  add column if not exists badge_gcc boolean not null default false,
  add column if not exists profile_complete boolean not null default false;

alter table public.jobs
  add column if not exists expires_at timestamptz,
  add column if not exists jd_quality_score integer check (jd_quality_score >= 0 and jd_quality_score <= 100),
  add column if not exists jd_quality_feedback text,
  add column if not exists featured boolean not null default false;

-- Expand job statuses
alter table public.jobs drop constraint if exists jobs_status_check;
alter table public.jobs add constraint jobs_status_check
  check (status in ('draft', 'active', 'paused', 'closed', 'archived'));

-- Multi-seat foundation (owner is implicit admin via companies.owner_id)
create table if not exists public.company_members (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  member_role text not null check (member_role in ('admin', 'recruiter', 'hiring_manager')),
  created_at timestamptz not null default now(),
  unique (company_id, user_id)
);

alter table public.company_members enable row level security;

create policy "company_members_select" on public.company_members
  for select using (
    exists (
      select 1 from public.companies c
      where c.id = company_id and c.owner_id = auth.uid()
    )
    or user_id = auth.uid()
  );

-- Company logos bucket
insert into storage.buckets (id, name, public)
values ('company-logos', 'company-logos', true)
on conflict (id) do nothing;

create policy "Employers upload company logo"
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'company-logos'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "Public read company logos"
on storage.objects for select
to public
using (bucket_id = 'company-logos');
