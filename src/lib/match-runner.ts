import { getServiceClient } from "@/lib/supabase/service";
import {
  combinedMatchScore,
  computeSkillOverlapScore,
  experienceScore,
  llmMatchReason,
} from "@/lib/matching";
import { MIN_MATCH_SCORE, notifyRecruitersForHighMatch } from "@/lib/recruiter-alert";
import type { CandidateProfile, Job } from "@/lib/types";

function getServiceClientForMatching() {
  return getServiceClient();
}

const MIN_MATCH_SCORE_LOCAL = MIN_MATCH_SCORE;

export async function runMatchingForCandidate(candidateProfileId: string) {
  const supabase = getServiceClientForMatching();
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

    if (score < MIN_MATCH_SCORE_LOCAL) continue;

    const reason =
      (await llmMatchReason(candidate as CandidateProfile, job, score)) ??
      `Skills overlap at ${skillScore}% with required stack.`;

    const { data: upserted, error } = await supabase.from("matches").upsert(
      {
        candidate_profile_id: candidateProfileId,
        job_id: job.id,
        match_score: score,
        match_reason: reason,
        status: "suggested",
        visible_to_employer: false,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "candidate_profile_id,job_id" },
    ).select("id").single();

    if (!error && upserted?.id) {
      matched += 1;
      await notifyRecruitersForHighMatch(upserted.id);
    }
  }

  return { matched };
}

export async function runMatchingForJob(jobId: string) {
  const supabase = getServiceClientForMatching();
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

    if (score < MIN_MATCH_SCORE_LOCAL) continue;

    const reason =
      (await llmMatchReason(candidate, job as Job, score)) ??
      `Skills overlap at ${skillScore}% with required stack.`;

    const { data: upserted, error } = await supabase.from("matches").upsert(
      {
        candidate_profile_id: candidate.id,
        job_id: jobId,
        match_score: score,
        match_reason: reason,
        status: "suggested",
        visible_to_employer: false,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "candidate_profile_id,job_id" },
    ).select("id").single();

    if (!error && upserted?.id) {
      matched += 1;
      await notifyRecruitersForHighMatch(upserted.id);
    }
  }

  return { matched };
}
