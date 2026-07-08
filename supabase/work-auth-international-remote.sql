-- Map legacy "other" work authorization to international remote
-- Run in Supabase SQL Editor after candidate-profile-v2.sql

update public.candidate_profiles
set work_authorization = 'international_remote'
where work_authorization = 'other';
