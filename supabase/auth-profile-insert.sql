-- Run in Supabase SQL Editor if Google sign-in shows profile_missing
-- Allows a user to create their own profile row when the auth trigger did not run

drop policy if exists "profiles_insert_own" on public.profiles;

create policy "profiles_insert_own"
  on public.profiles
  for insert
  with check (auth.uid() = id);
