-- Fix: infinite recursion in profiles RLS policies
-- Admin policies queried public.profiles inside profiles RLS, which re-triggered the same check.
-- Run this in the Supabase SQL Editor (safe to run multiple times).

create or replace function public.is_admin()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1
    from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

grant execute on function public.is_admin() to authenticated;

-- Handoff queue policies
drop policy if exists "handoffs_admin_select" on public.handoff_requests;
create policy "handoffs_admin_select" on public.handoff_requests
  for select using (public.is_admin());

drop policy if exists "handoffs_admin_update" on public.handoff_requests;
create policy "handoffs_admin_update" on public.handoff_requests
  for update using (public.is_admin());

drop policy if exists "matches_select_admin" on public.matches;
create policy "matches_select_admin" on public.matches
  for select using (public.is_admin());

drop policy if exists "jobs_select_admin" on public.jobs;
create policy "jobs_select_admin" on public.jobs
  for select using (public.is_admin());

drop policy if exists "companies_select_admin" on public.companies;
create policy "companies_select_admin" on public.companies
  for select using (public.is_admin());

drop policy if exists "candidate_profiles_select_admin" on public.candidate_profiles;
create policy "candidate_profiles_select_admin" on public.candidate_profiles
  for select using (public.is_admin());

drop policy if exists "profiles_select_admin" on public.profiles;
create policy "profiles_select_admin" on public.profiles
  for select using (public.is_admin());

-- Match review policy
drop policy if exists "matches_update_admin" on public.matches;
create policy "matches_update_admin" on public.matches
  for update using (public.is_admin());
