-- Run this once in Supabase: SQL Editor → New query → Run
-- This lets the form save using only your publishable/anon key (no service role needed)

alter table public.role_submissions
add column if not exists submission_type text not null default 'manual_form';

drop policy if exists "Allow public inserts" on public.role_submissions;

create policy "Allow public inserts"
on public.role_submissions
for insert
to public
with check (true);
