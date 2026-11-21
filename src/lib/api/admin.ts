/**
 * Admin Dashboard API Module for Django REST Framework.
 * Phase 18 — Admin Dashboard Analytics & Monitoring.
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

export interface AdminRecentCandidatePreview {
  id: string;
  name: string;
  email: string;
  currentTitle: string;
  completeness: number;
  availability: string;
  createdAt: string;
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
  pendingMatches: number;

  // Previews
  pendingMatchPreviews: AdminMatchPreview[];
  recentCandidatePreviews?: AdminRecentCandidatePreview[];
  unmatchedJobPreviews: AdminUnmatchedJobPreview[];
  incompleteProfilePreviews: AdminIncompleteProfilePreview[];
}

export interface SystemFeatureToggleItem {
  feature_key: string;
  name: string;
  description: string;
  is_enabled: boolean;
  effective_status: boolean;
  environment_master_switch: boolean;
  updated_at: string | null;
  updated_by: {
    id: string;
    email: string;
  } | null;
}

export interface SystemFeatureToggleListResponse {
  features: SystemFeatureToggleItem[];
}

export const adminApi = {
  /**
   * Retrieves aggregated dashboard analytics and previews.
   * Admin-only access.
   */
  async getDashboardStats(options?: RequestOptions): Promise<DjangoAdminDashboardStats> {
    return djangoApi.get<DjangoAdminDashboardStats>("/api/v1/admin/dashboard/stats/", options);
  },

  /**
   * Lists all system feature toggles with effective state and metadata.
   */
  async getFeatureToggles(options?: RequestOptions): Promise<SystemFeatureToggleListResponse> {
    return djangoApi.get<SystemFeatureToggleListResponse>("/api/v1/admin/features/", options);
  },

  /**
   * Updates an administrative feature toggle.
   */
  async updateFeatureToggle(
    featureKey: string,
    isEnabled: boolean,
    options?: RequestOptions,
  ): Promise<SystemFeatureToggleItem> {
    return djangoApi.patch<SystemFeatureToggleItem>(
      `/api/v1/admin/features/${featureKey}/`,
      { is_enabled: isEnabled },
      options,
    );
  },
};

