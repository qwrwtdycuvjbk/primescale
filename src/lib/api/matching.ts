/**
 * Matching and Handoffs API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoMatch {
  id: string;
  candidate_profile_id?: string;
  job_id?: string;
  job_title?: string;
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
  recruiter_notified_at?: string | null;
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
    work_type?: string;
    company_name?: string;
    company_logo_url?: string;
    companies?: {
      name?: string;
      logo_url?: string;
    };
    company?: {
      id?: string;
      name: string;
      logo_url?: string;
    };
  };
  jobs?: {
    id: string;
    title: string;
    description?: string;
    tech_stack?: string[];
    salary_range?: string;
    experience_level?: string;
    role_type?: string;
    work_type?: string;
    company_name?: string;
    company_logo_url?: string;
    companies?: {
      name?: string;
      logo_url?: string;
    };
  };
  candidate_profile?: {
    id: string;
    full_name?: string;
    email?: string;
    headline?: string;
    current_title?: string;
    years_experience?: number;
    skills?: string[];
    experience_level?: string;
    work_authorization?: string;
    us_state?: string;
    remote_preference?: string;
    linkedin_url?: string;
    github_url?: string;
    portfolio_url?: string;
    resume_url?: string;
    profiles?: {
      full_name?: string;
      email?: string;
    };
    user?: {
      id?: string;
      full_name: string;
      email: string;
      phone?: string;
    };
  };
  candidate_profiles?: {
    id: string;
    full_name?: string;
    email?: string;
    headline?: string;
    current_title?: string;
    years_experience?: number;
    skills?: string[];
    experience_level?: string;
    work_authorization?: string;
    us_state?: string;
    remote_preference?: string;
    linkedin_url?: string;
    github_url?: string;
    portfolio_url?: string;
    resume_url?: string;
    profiles?: {
      full_name?: string;
      email?: string;
    };
  };
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

export type { DjangoHandoff } from "./handoffs";
export { handoffsApi } from "./handoffs";
