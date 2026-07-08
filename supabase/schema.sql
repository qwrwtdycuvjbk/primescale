-- Legacy public "Post a role" form storage (OPTIONAL — skip if table already exists)
-- Not required for marketplace auth, admin portal, or candidate profiles.
-- If you see "role_submissions already exists", do NOT run this file.

do $$
begin
  create table public.role_submissions (
    id uuid primary key default gen_random_uuid(),
    created_at date not null default current_date,
    company_name text not null,
    contact_name text not null,
    email text not null,
    phone text not null,
    job_title text not null,
    role_type text not null,
    experience_level text not null,
    tech_stack text not null,
    salary_range text,
    description text not null,
    notes text,
    submission_type text not null default 'manual_form'
  );
exception
  when duplicate_table then null;
end $$;

alter table public.role_submissions enable row level security;

drop policy if exists "Allow public inserts" on public.role_submissions;

create policy "Allow public inserts"
on public.role_submissions
for insert
to anon
with check (true);
