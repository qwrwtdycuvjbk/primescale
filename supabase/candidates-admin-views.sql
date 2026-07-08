-- Admin-friendly candidate views for Supabase Table Editor
-- Run after marketplace-schema.sql and candidate-profile-v2.sql
--
-- In Supabase: Table Editor → pick "candidates_overview" or "candidate_applications"
-- Candidate name is the first column, followed by date (no time).

-- All candidates who signed up and built a profile
create or replace view public.candidates_overview
with (security_invoker = true) as
select
  p.full_name as candidate_name,
  cp.created_at::date as signed_up_date,
  cp.updated_at::date as profile_updated_date,
  p.email as candidate_email,
  coalesce(cp.phone, p.phone) as candidate_phone,
  cp.current_title,
  cp.headline,
  cp.experience_level,
  cp.years_experience,
  cp.work_authorization,
  cp.us_state,
  cp.availability_status,
  cp.profile_complete,
  cp.profile_completeness,
  cp.open_to_matching,
  cp.linkedin_url,
  cp.github_url,
  cp.resume_url,
  cp.id as candidate_profile_id,
  cp.user_id
from public.candidate_profiles cp
join public.profiles p on p.id = cp.user_id
where p.role = 'candidate';

-- Candidates who applied / showed interest in a role (matches)
create or replace view public.candidate_applications
with (security_invoker = true) as
select
  p.full_name as candidate_name,
  m.created_at::date as applied_date,
  m.updated_at::date as last_updated_date,
  m.status as application_status,
  m.match_score,
  j.title as job_title,
  c.name as company_name,
  p.email as candidate_email,
  coalesce(cp.phone, p.phone) as candidate_phone,
  cp.current_title,
  cp.headline,
  m.match_reason,
  m.visible_to_employer,
  m.id as match_id,
  cp.id as candidate_profile_id,
  j.id as job_id
from public.matches m
join public.candidate_profiles cp on cp.id = m.candidate_profile_id
join public.profiles p on p.id = cp.user_id
join public.jobs j on j.id = m.job_id
join public.companies c on c.id = j.company_id;

grant select on public.candidates_overview to authenticated;
grant select on public.candidate_applications to authenticated;
