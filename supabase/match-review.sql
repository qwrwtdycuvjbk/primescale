-- Recruiter review gate: high-confidence matches alert People Prime first
-- Run in Supabase SQL Editor after handoff-queue.sql

alter table public.matches
  add column if not exists visible_to_employer boolean not null default false;

alter table public.matches
  add column if not exists recruiter_notified_at timestamptz;

create index if not exists matches_recruiter_review_idx
  on public.matches (visible_to_employer, match_score desc);

-- Admins can update matches (approve for employer view)
create policy "matches_update_admin" on public.matches
  for update using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'admin'
    )
  );
