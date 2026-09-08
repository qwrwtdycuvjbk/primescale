/**
 * Matching and Handoffs API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoMatch {
  id: string;
  candidate_profile_id?: string;
  job_id?: string;
  match_score: number;
  skill_score?: number;
  experience_score?: number;
  match_reason?: string | null;
  status:
    | "suggested"
    | "admin_approved"
    | "candidate_interested"
    | "employer_shortlisted"
    | "mutual_fit"
    | "rejected";
  visible_to_employer: boolean;
  created_at?: string;
  updated_at?: string;
  job?: {
    id: string;
    title: string;
    description?: string;
    tech_stack?: string[];
    salary_range?: string;
    experience_level?: string;
    role_type?: string;
    company?: {
      id?: string;
      name: string;
      logo_url?: string;
    };
  };
  candidate_profile?: {
    id: string;
    headline?: string;
    skills?: string[];
    experience_level?: string;
    user?: {
      id?: string;
      full_name: string;
      email: string;
      phone?: string;
    };
  };
}

export interface DjangoHandoff {
  id: string;
  match: DjangoMatch;
  status: "pending" | "contacted" | "intro_made" | "closed";
  notes?: string | null;
  notified_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface MatchFilterParams {
  status?: string;
  job_id?: string;
  visible_to_employer?: boolean;
}

export const matchingApi = {
  /**
   * List matches based on role and query parameters
   */
  async listMatches(params?: MatchFilterParams, options?: RequestOptions): Promise<DjangoMatch[]> {
    return djangoApi.get<DjangoMatch[]>("/api/v1/matches/", {
      ...options,
      params: params as Record<string, string | number | boolean | undefined>,
    });
  },

  /**
   * Get single match detail
   */
  async getMatch(id: string, options?: RequestOptions): Promise<DjangoMatch> {
    return djangoApi.get<DjangoMatch>(`/api/v1/matches/${id}/`, options);
  },

  /**
   * Update match status (candidate interest, employer shortlist, reject)
   */
  async updateMatchStatus(
    id: string,
    status: "candidate_interested" | "employer_shortlisted" | "rejected",
    options?: RequestOptions,
  ): Promise<{ ok: boolean; status: string }> {
    return djangoApi.patch<{ ok: boolean; status: string }>(
      `/api/v1/matches/${id}/`,
      { status },
      options,
    );
  },

  /**
   * Admin approve or reject match gate
   */
  async adminMatchAction(
    id: string,
    action: "approve" | "reject",
    options?: RequestOptions,
  ): Promise<{ ok: boolean }> {
    return djangoApi.patch<{ ok: boolean }>(
      `/api/v1/matches/${id}/admin-action/`,
      { action },
      options,
    );
  },
};

export const handoffsApi = {
  /**
   * Admin-only queue of mutual fit handoffs
   */
  async listHandoffs(status?: string, options?: RequestOptions): Promise<DjangoHandoff[]> {
    return djangoApi.get<DjangoHandoff[]>("/api/v1/handoffs/", {
      ...options,
      params: status ? { status } : undefined,
    });
  },

  /**
   * Admin-only get single handoff
   */
  async getHandoff(id: string, options?: RequestOptions): Promise<DjangoHandoff> {
    return djangoApi.get<DjangoHandoff>(`/api/v1/handoffs/${id}/`, options);
  },

  /**
   * Admin-only update handoff status & notes
   */
  async updateHandoff(
    id: string,
    data: { status?: "pending" | "contacted" | "intro_made" | "closed"; notes?: string },
    options?: RequestOptions,
  ): Promise<{ ok: boolean; handoff: DjangoHandoff }> {
    return djangoApi.patch<{ ok: boolean; handoff: DjangoHandoff }>(
      `/api/v1/handoffs/${id}/`,
      data,
      options,
    );
  },
};
