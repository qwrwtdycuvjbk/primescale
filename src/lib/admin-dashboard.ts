import { cache } from "react";
import { MIN_MATCH_SCORE } from "@/lib/constants";
import { adminApi, handoffsApi, matchingApi } from "@/lib/api";
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

/** Deduped per request for AdminShell navigation counters */
export const loadAdminNavCounts = cache(async (): Promise<AdminNavCounts> => {
  try {
    const token = await getAccessToken();
    const [matches, handoffs] = await Promise.all([
      matchingApi.listMatches({ visible_to_employer: false }, { token }),
      handoffsApi.listHandoffs("pending", { token }),
    ]);

    const pendingMatches = matches
      ? matches.filter(
          (m) =>
            m.visible_to_employer === false &&
            m.match_score >= MIN_MATCH_SCORE &&
            m.status !== "rejected",
        ).length
      : 0;

    const pendingHandoffs = handoffs ? handoffs.length : 0;

    return {
      pendingMatches,
      pendingHandoffs,
    };
  } catch (err) {
    console.error("Failed to load admin nav counts:", err);
    return {
      pendingMatches: 0,
      pendingHandoffs: 0,
    };
  }
});

export async function loadAdminDashboardStats(): Promise<AdminDashboardStats> {
  try {
    const token = await getAccessToken();
    const djangoStats = await adminApi.getDashboardStats({ token });
    if (djangoStats) {
      return djangoStats;
    }
  } catch (err) {
    console.error("Failed to load admin dashboard stats:", err);
  }

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
