-- Run this in Supabase SQL Editor to fix Google OAuth sign-in loops
-- Safe to run multiple times

-- 1) Let users create their own profile if the auth trigger missed
drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles
  for insert
  with check (auth.uid() = id);

-- 2) Fix trigger to read Google "name" metadata
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, role, full_name, email, phone)
  values (
    new.id,
    coalesce(nullif(new.raw_user_meta_data->>'role', ''), 'candidate'),
    coalesce(
      nullif(new.raw_user_meta_data->>'full_name', ''),
      nullif(new.raw_user_meta_data->>'name', ''),
      split_part(coalesce(new.email, ''), '@', 1),
      'User'
    ),
    coalesce(new.email, ''),
    nullif(new.raw_user_meta_data->>'phone', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

-- 3) Callable after OAuth — creates or repairs the profile row
create or replace function public.ensure_user_profile(p_role text default null)
returns public.profiles
language plpgsql
security definer
set search_path = public
as $$
declare
  uid uuid := auth.uid();
  u record;
  chosen_role text;
  chosen_name text;
  chosen_phone text;
  row public.profiles;
begin
  if uid is null then
    raise exception 'Not authenticated';
  end if;

  select id, email, raw_user_meta_data
  into u
  from auth.users
  where id = uid;

  chosen_role := coalesce(
    nullif(p_role, ''),
    nullif(u.raw_user_meta_data->>'role', ''),
    'candidate'
  );

  if chosen_role not in ('employer', 'candidate', 'admin') then
    chosen_role := 'candidate';
  end if;

  chosen_name := coalesce(
    nullif(u.raw_user_meta_data->>'full_name', ''),
    nullif(u.raw_user_meta_data->>'name', ''),
    nullif(split_part(coalesce(u.email, ''), '@', 1), ''),
    'User'
  );

  chosen_phone := nullif(u.raw_user_meta_data->>'phone', '');

  insert into public.profiles (id, role, full_name, email, phone)
  values (uid, chosen_role, chosen_name, coalesce(u.email, ''), chosen_phone)
  on conflict (id) do update
  set
    role = case
      when p_role in ('employer', 'candidate', 'admin') then p_role
      else profiles.role
    end,
    full_name = coalesce(nullif(profiles.full_name, ''), excluded.full_name),
    email = coalesce(nullif(profiles.email, ''), excluded.email),
    phone = coalesce(nullif(profiles.phone, ''), excluded.phone)
  returning * into row;

  return row;
end;
$$;

grant execute on function public.ensure_user_profile(text) to authenticated;
