-- Run in Supabase SQL Editor to show only day/month/year (no time)

alter table public.role_submissions
alter column created_at type date using created_at::date;

alter table public.role_submissions
alter column created_at set default current_date;
