-- Track where candidates came from (platform signup vs People Prime manual add)
alter table public.candidate_profiles
  add column if not exists source text not null default 'platform'
    check (source in ('platform', 'people_prime'));

create index if not exists candidate_profiles_source_idx on public.candidate_profiles(source);
