import { createClient } from "@supabase/supabase-js";
import {
  combinedMatchScore,
  computeSkillOverlapScore,
  experienceScore,
  llmMatchReason,
} from "@/lib/matching";
import type { CandidateProfile, Job } from "@/lib/types";

function getServiceClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key);
}

const MIN_MATCH_SCORE = 45;

export async function runMatchingForCandidate(candidateProfileId: string) {
  const supabase = getServiceClient();
  if (!supabase) return { matched: 0 };

  const { data: candidate } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("id", candidateProfileId)
    .eq("open_to_matching", true)
    .eq("profile_complete", true)
    .single();

  if (!candidate) return { matched: 0 };

  const { data: jobs } = await supabase
    .from("jobs")
    .select("*")
    .eq("status", "active");

  if (!jobs?.length) return { matched: 0 };

  let matched = 0;

  for (const job of jobs as Job[]) {
    const skillScore = computeSkillOverlapScore(
      candidate.skills,
      job.tech_stack,
    );
    const expScore = experienceScore(
      candidate.experience_level,
      job.experience_level,
    );
    const score = combinedMatchScore(skillScore, expScore);

    if (score < MIN_MATCH_SCORE) continue;

    const reason =
      (await llmMatchReason(candidate as CandidateProfile, job, score)) ??
      `Skills overlap at ${skillScore}% with required stack.`;

    const { error } = await supabase.from("matches").upsert(
      {
        candidate_profile_id: candidateProfileId,
        job_id: job.id,
        match_score: score,
        match_reason: reason,
        status: "suggested",
        updated_at: new Date().toISOString(),
      },
      { onConflict: "candidate_profile_id,job_id" },
    );

    if (!error) matched += 1;
  }

  return { matched };
}

export async function runMatchingForJob(jobId: string) {
  const supabase = getServiceClient();
  if (!supabase) return { matched: 0 };

  const { data: job } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", jobId)
    .eq("status", "active")
    .single();

  if (!job) return { matched: 0 };

  const { data: candidates } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("open_to_matching", true)
    .eq("profile_complete", true);

  if (!candidates?.length) return { matched: 0 };

  let matched = 0;

  for (const candidate of candidates as CandidateProfile[]) {
    const skillScore = computeSkillOverlapScore(
      candidate.skills,
      job.tech_stack,
    );
    const expScore = experienceScore(
      candidate.experience_level,
      job.experience_level,
    );
    const score = combinedMatchScore(skillScore, expScore);

    if (score < MIN_MATCH_SCORE) continue;

    const reason =
      (await llmMatchReason(candidate, job as Job, score)) ??
      `Skills overlap at ${skillScore}% with required stack.`;

    const { error } = await supabase.from("matches").upsert(
      {
        candidate_profile_id: candidate.id,
        job_id: jobId,
        match_score: score,
        match_reason: reason,
        status: "suggested",
        updated_at: new Date().toISOString(),
      },
      { onConflict: "candidate_profile_id,job_id" },
    );

    if (!error) matched += 1;
  }

  return { matched };
}
