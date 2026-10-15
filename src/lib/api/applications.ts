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
    if (typeof window !== "undefined" && !options?.token) {
      const search = new URLSearchParams();
      if (params?.job_id) search.set("job_id", params.job_id);
      if (params?.status) search.set("status", params.status);
      const query = search.toString();
      const res = await fetch(`/api/applications${query ? `?${query}` : ""}`, { cache: "no-store" });
      if (!res.ok) return [];
      const data = await res.json();
      return data.applications || [];
    }
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
    if (typeof window !== "undefined" && !options?.token) {
      const res = await fetch("/api/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId, coverNote }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to submit application");
      }
      return data;
    }
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
