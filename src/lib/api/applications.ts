/**
 * Applications API Module for Django REST Framework.
 * Phase 17 — Job Applications Migration.
 */

import { djangoApi, RequestOptions } from "./client";
import type { DjangoMatch } from "./matching";

export interface DjangoApplication extends DjangoMatch {
  applied_at?: string;
}

export interface ApplicationFilterParams {
  status?: string;
  job_id?: string;
}

export const applicationsApi = {
  /**
   * List applications based on user role (candidate, employer, admin)
   */
  async listApplications(
    params?: ApplicationFilterParams,
    options?: RequestOptions,
  ): Promise<DjangoApplication[]> {
    return djangoApi.get<DjangoApplication[]>("/api/v1/applications/", {
      ...options,
      params: params as Record<string, string | number | boolean | undefined>,
    });
  },

  /**
   * Get single application detail with IDOR verification
   */
  async getApplication(id: string, options?: RequestOptions): Promise<DjangoApplication> {
    return djangoApi.get<DjangoApplication>(`/api/v1/applications/${id}/`, options);
  },

  /**
   * Candidate applies to an active job
   */
  async apply(
    jobId: string,
    coverNote?: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; application: DjangoApplication }> {
    return djangoApi.post<{ ok: boolean; application: DjangoApplication }>(
      "/api/v1/applications/apply/",
      { job_id: jobId, cover_note: coverNote },
      options,
    );
  },

  /**
   * Update application status (shortlist, reject)
   */
  async updateStatus(
    id: string,
    status: "employer_shortlisted" | "rejected",
    notes?: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; status: string; application: DjangoApplication }> {
    return djangoApi.patch<{ ok: boolean; status: string; application: DjangoApplication }>(
      `/api/v1/applications/${id}/`,
      { status, notes },
      options,
    );
  },
};
