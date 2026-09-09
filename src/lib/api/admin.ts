/**
 * Admin Dashboard API Module for Django REST Framework.
 * Phase 18 — Admin Dashboard Analytics.
 */

import { djangoApi, RequestOptions } from "./client";

export interface AdminMatchPreview {
  id: string;
  matchScore: number;
  status: string;
  candidateName: string;
  jobTitle: string;
  companyName: string;
}

export interface AdminHandoffPreview {
  id: string;
  candidateName: string;
  jobTitle: string;
  companyName: string;
}

export interface AdminUnmatchedJobPreview {
  id: string;
  title: string;
  companyName: string;
  postedAt: string;
}

export interface AdminIncompleteProfilePreview {
  id: string;
  name: string;
  email: string;
  signedUpAt: string;
}

export interface DjangoAdminDashboardStats {
  pendingMatches: number;
  pendingHandoffs: number;
  newCandidatesThisWeek: number;
  newEmployersThisWeek: number;
  activeJobsWithNoMatches: number;
  incompleteProfiles: number;
  candidateInterested: number;
  pendingMatchPreviews: AdminMatchPreview[];
  candidateInterestPreviews: AdminMatchPreview[];
  pendingHandoffPreviews: AdminHandoffPreview[];
  unmatchedJobPreviews: AdminUnmatchedJobPreview[];
  incompleteProfilePreviews: AdminIncompleteProfilePreview[];
}

export const adminApi = {
  /**
   * Retrieves aggregated dashboard analytics and previews.
   * Admin-only access.
   */
  async getDashboardStats(options?: RequestOptions): Promise<DjangoAdminDashboardStats> {
    return djangoApi.get<DjangoAdminDashboardStats>("/api/v1/admin/dashboard/stats/", options);
  },
};
