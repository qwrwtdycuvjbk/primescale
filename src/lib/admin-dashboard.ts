import { cache } from "react";
import { MIN_MATCH_SCORE } from "@/lib/recruiter-alert";
import { getAdminClient } from "@/lib/supabase/admin";

export function startOfWeekIso(): string {
  const now = new Date();
  const day = now.getDay();
  const daysFromMonday = day === 0 ? 6 : day - 1;
  const monday = new Date(now);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(now.getDate() - daysFromMonday);
  return monday.toISOString();
}

export type AdminNavCounts = {
  pendingMatches: number;
  pendingHandoffs: number;
};

export type AdminDashboardStats = AdminNavCounts & {
  newCandidatesThisWeek: number;
  newEmployersThisWeek: number;
  activeJobsWithNoMatches: number;
  incompleteProfiles: number;
  candidateInterested: number;
  pendingMatchPreviews: {
    id: string;
    matchScore: number;
    status: string;
    candidateName: string;
    jobTitle: string;
    companyName: string;
  }[];
  candidateInterestPreviews: {
    id: string;
    matchScore: number;
    candidateName: string;
    jobTitle: string;
    companyName: string;
  }[];
  pendingHandoffPreviews: {
    id: string;
    candidateName: string;
    jobTitle: string;
    companyName: string;
  }[];
  unmatchedJobPreviews: {
    id: string;
    title: string;
    companyName: string;
    postedAt: string;
  }[];
  incompleteProfilePreviews: {
    id: string;
    name: string;
    email: string;
    signedUpAt: string;
  }[];
};

/** Deduped per request so AdminShell + dashboard don't hit Supabase twice. */
export const loadAdminNavCounts = cache(async (): Promise<AdminNavCounts> => {
  const supabase = await getAdminClient();
  if (!supabase) {
    return { pendingMatches: 0, pendingHandoffs: 0 };
  }

  const [{ count: pendingMatches }, { count: pendingHandoffs }] = await Promise.all([
    supabase
      .from("matches")
      .select("id", { count: "exact", head: true })
      .eq("visible_to_employer", false)
      .gte("match_score", MIN_MATCH_SCORE)
      .neq("status", "rejected"),
    supabase
      .from("handoff_requests")
      .select("id", { count: "exact", head: true })
      .eq("status", "pending"),
  ]);

  return {
    pendingMatches: pendingMatches ?? 0,
    pendingHandoffs: pendingHandoffs ?? 0,
  };
});

export async function loadAdminDashboardStats(): Promise<AdminDashboardStats> {
  const supabase = await getAdminClient();
  const weekStart = startOfWeekIso();

  if (!supabase) {
    return {
      pendingMatches: 0,
      pendingHandoffs: 0,
      newCandidatesThisWeek: 0,
      newEmployersThisWeek: 0,
      activeJobsWithNoMatches: 0,
      incompleteProfiles: 0,
      candidateInterested: 0,
      pendingMatchPreviews: [],
      candidateInterestPreviews: [],
      pendingHandoffPreviews: [],
      unmatchedJobPreviews: [],
      incompleteProfilePreviews: [],
    };
  }

  const [
    navCounts,
    { count: newCandidatesThisWeek },
    { count: newEmployersThisWeek },
    { data: pendingMatches },
    { count: candidateInterested },
    { data: interestedMatches },
    { data: pendingHandoffs },
    { data: activeJobs },
    { data: incompleteCandidates },
    { count: incompleteProfiles },
  ] = await Promise.all([
    loadAdminNavCounts(),
    supabase
      .from("profiles")
      .select("*", { count: "exact", head: true })
      .eq("role", "candidate")
      .gte("created_at", weekStart),
    supabase
      .from("profiles")
      .select("*", { count: "exact", head: true })
      .eq("role", "employer")
      .gte("created_at", weekStart),
    supabase
      .from("matches")
      .select(
        `
        id,
        match_score,
        status,
        jobs ( title, companies ( name ) ),
        candidate_profiles ( profiles ( full_name ) )
      `,
      )
      .eq("visible_to_employer", false)
      .gte("match_score", MIN_MATCH_SCORE)
      .neq("status", "rejected")
      .order("match_score", { ascending: false })
      .limit(5),
    supabase
      .from("matches")
      .select("id", { count: "exact", head: true })
      .eq("status", "candidate_interested"),
    supabase
      .from("matches")
      .select(
        `
        id,
        match_score,
        jobs ( title, companies ( name ) ),
        candidate_profiles ( profiles ( full_name ) )
      `,
      )
      .eq("status", "candidate_interested")
      .order("updated_at", { ascending: false })
      .limit(5),
    supabase
      .from("handoff_requests")
      .select(
        `
        id,
        matches (
          jobs ( title, companies ( name ) ),
          candidate_profiles ( profiles ( full_name ) )
        )
      `,
      )
      .eq("status", "pending")
      .order("created_at", { ascending: false })
      .limit(5),
    supabase
      .from("jobs")
      .select("id, title, created_at, companies ( name ), matches ( id )")
      .eq("status", "active")
      .order("created_at", { ascending: false })
      .limit(100),
    supabase
      .from("candidate_profiles")
      .select("id, created_at, profiles!inner ( full_name, email, role )")
      .eq("profiles.role", "candidate")
      .eq("profile_complete", false)
      .order("created_at", { ascending: false })
      .limit(5),
    supabase
      .from("candidate_profiles")
      .select("id, profiles!inner(role)", { count: "exact", head: true })
      .eq("profiles.role", "candidate")
      .eq("profile_complete", false),
  ]);

  const unmatchedJobs = (activeJobs ?? []).filter((job) => {
    const matches = job.matches;
    if (!matches) return true;
    return Array.isArray(matches) ? matches.length === 0 : false;
  });

  function mapMatchPreview(match: {
    id: string;
    match_score: number;
    status?: string;
    jobs: unknown;
    candidate_profiles: unknown;
  }) {
    const jobRaw = match.jobs;
    const job = Array.isArray(jobRaw) ? jobRaw[0] : jobRaw;
    const companyRaw = job?.companies;
    const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;
    const candidateRaw = match.candidate_profiles;
    const candidate = Array.isArray(candidateRaw) ? candidateRaw[0] : candidateRaw;
    const profileRaw = candidate?.profiles;
    const profile = Array.isArray(profileRaw) ? profileRaw[0] : profileRaw;

    return {
      id: match.id,
      matchScore: match.match_score,
      status: match.status ?? "suggested",
      candidateName: profile?.full_name ?? "Candidate",
      jobTitle: job?.title ?? "Role",
      companyName: company?.name ?? "Company",
    };
  }

  return {
    ...navCounts,
    newCandidatesThisWeek: newCandidatesThisWeek ?? 0,
    newEmployersThisWeek: newEmployersThisWeek ?? 0,
    activeJobsWithNoMatches: unmatchedJobs.length,
    incompleteProfiles: incompleteProfiles ?? 0,
    candidateInterested: candidateInterested ?? 0,
    pendingMatchPreviews: (pendingMatches ?? []).map(mapMatchPreview),
    candidateInterestPreviews: (interestedMatches ?? []).map((match) => {
      const preview = mapMatchPreview(match);
      return {
        id: preview.id,
        matchScore: preview.matchScore,
        candidateName: preview.candidateName,
        jobTitle: preview.jobTitle,
        companyName: preview.companyName,
      };
    }),
    pendingHandoffPreviews: (pendingHandoffs ?? []).map((handoff) => {
      const matchRaw = handoff.matches;
      const match = Array.isArray(matchRaw) ? matchRaw[0] : matchRaw;
      const jobRaw = match?.jobs;
      const job = Array.isArray(jobRaw) ? jobRaw[0] : jobRaw;
      const companyRaw = job?.companies;
      const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;
      const candidateRaw = match?.candidate_profiles;
      const candidate = Array.isArray(candidateRaw) ? candidateRaw[0] : candidateRaw;
      const profileRaw = candidate?.profiles;
      const profile = Array.isArray(profileRaw) ? profileRaw[0] : profileRaw;

      return {
        id: handoff.id,
        candidateName: profile?.full_name ?? "Candidate",
        jobTitle: job?.title ?? "Role",
        companyName: company?.name ?? "Company",
      };
    }),
    unmatchedJobPreviews: unmatchedJobs.slice(0, 5).map((job) => {
      const companyRaw = job.companies;
      const company = Array.isArray(companyRaw) ? companyRaw[0] : companyRaw;

      return {
        id: job.id,
        title: job.title,
        companyName: company?.name ?? "Company",
        postedAt: job.created_at,
      };
    }),
    incompleteProfilePreviews: (incompleteCandidates ?? []).map((row) => {
      const profileRaw = row.profiles;
      const profile = Array.isArray(profileRaw) ? profileRaw[0] : profileRaw;

      return {
        id: row.id,
        name: profile?.full_name ?? "Candidate",
        email: profile?.email ?? "",
        signedUpAt: row.created_at,
      };
    }),
  };
}
