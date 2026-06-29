-- Run after marketplace-schema.sql — extends candidate profiles for SRS fields

alter table public.candidate_profiles
  add column if not exists phone text,
  add column if not exists current_title text,
  add column if not exists years_experience integer,
  add column if not exists github_url text,
  add column if not exists portfolio_url text,
  add column if not exists linkedin_url text,
  add column if not exists availability_status text not null default 'actively_looking'
    check (availability_status in ('actively_looking', 'open', 'not_looking')),
  add column if not exists preferred_work_type text not null default 'remote'
    check (preferred_work_type in ('remote', 'hybrid', 'onsite')),
  add column if not exists privacy_visibility text not null default 'employers_only'
    check (privacy_visibility in ('public', 'employers_only', 'invite_only')),
  add column if not exists profile_completeness integer not null default 0
    check (profile_completeness >= 0 and profile_completeness <= 100);

-- Resume storage bucket (run in Supabase dashboard or via SQL if storage enabled)
insert into storage.buckets (id, name, public)
values ('resumes', 'resumes', false)
on conflict (id) do nothing;

create policy "Candidates upload own resume"
on storage.objects for insert
to authenticated
with check (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "Candidates read own resume"
on storage.objects for select
to authenticated
using (
  bucket_id = 'resumes'
  and (storage.foldername(name))[1] = auth.uid()::text
);
