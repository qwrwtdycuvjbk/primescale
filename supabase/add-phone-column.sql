-- Run this once in Supabase: SQL Editor → New query → Run

alter table public.role_submissions
add column if not exists phone text not null default '';
