import { cache } from "react";
import { MIN_MATCH_SCORE } from "@/lib/constants";
import { adminApi, matchingApi } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

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
};

export type AdminDashboardStats = AdminNavCounts & {
  // Candidate Stats
  totalCandidates: number;
  completedProfiles: number;
  incompleteProfiles: number;
  candidatesWithResume: number;
  candidatesWithoutResume: number;
  candidatesAvailable: number;
  candidatesOpenToMatching: number;
  newCandidatesThisWeek: number;

  // Account Stats
  totalCandidateAccounts: number;
  totalEmployerAccounts: number;
  newEmployersThisWeek: number;

  // Job Stats
  totalInternalJobs: number;
  activeJobs: number;
  closedJobs: number;
  draftJobs: number;
  totalExternalJobs: number;
  activeJobsWithNoMatches: number;

  // Application Stats
  totalApplications: number;
  candidateInterested: number;
  employerShortlisted: number;
  mutualFit: number;
  rejectedApplications: number;

  // Matching Stats
  totalMatches: number;
  highConfidenceMatches: number;

  // Previews
  pendingMatchPreviews: {
    id: string;
    matchScore: number;
    status: string;
    candidateName: string;
    jobTitle: string;
    companyName: string;
  }[];
  recentCandidatePreviews?: {
    id: string;
    name: string;
    email: string;
    currentTitle: string;
    completeness: number;
    availability: string;
    createdAt: string;
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

/** Deduped per request for AdminShell navigation counters */
export const loadAdminNavCounts = cache(async (): Promise<AdminNavCounts> => {
  try {
    const token = await getAccessToken();
    const matches = await matchingApi.listMatches({ visible_to_employer: false }, { token });

    const pendingMatches = matches
      ? matches.filter(
          (m) =>
            m.visible_to_employer === false &&
            m.match_score >= MIN_MATCH_SCORE &&
            m.status !== "rejected",
        ).length
      : 0;

    return {
      pendingMatches,
    };
  } catch (err) {
    console.error("Failed to load admin nav counts:", err);
    return {
      pendingMatches: 0,
    };
  }
});

export async function loadAdminDashboardStats(): Promise<AdminDashboardStats> {
  try {
    const token = await getAccessToken();
    const djangoStats = await adminApi.getDashboardStats({ token });
    if (djangoStats) {
      return djangoStats as AdminDashboardStats;
    }
  } catch (err) {
    console.error("Failed to load admin dashboard stats:", err);
  }

  return {
    pendingMatches: 0,
    totalCandidates: 0,
    completedProfiles: 0,
    incompleteProfiles: 0,
    candidatesWithResume: 0,
    candidatesWithoutResume: 0,
    candidatesAvailable: 0,
    candidatesOpenToMatching: 0,
    newCandidatesThisWeek: 0,
    totalCandidateAccounts: 0,
    totalEmployerAccounts: 0,
    newEmployersThisWeek: 0,
    totalInternalJobs: 0,
    activeJobs: 0,
    closedJobs: 0,
    draftJobs: 0,
    totalExternalJobs: 0,
    activeJobsWithNoMatches: 0,
    totalApplications: 0,
    candidateInterested: 0,
    employerShortlisted: 0,
    mutualFit: 0,
    rejectedApplications: 0,
    totalMatches: 0,
    highConfidenceMatches: 0,
    pendingMatchPreviews: [],
    recentCandidatePreviews: [],
    unmatchedJobPreviews: [],
    incompleteProfilePreviews: [],
  };
}
