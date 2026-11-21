/**
 * Candidates API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoCandidateProfile {
  id: string;
  user_id?: string;
  user_email?: string;
  user_full_name?: string;
  user_is_active?: boolean;
  email?: string;
  full_name?: string;
  name?: string;
  is_active?: boolean;
  user?: {
    id?: string;
    email?: string;
    full_name?: string;
    is_active?: boolean;
  };
  profiles?: {
    id?: string;
    email?: string;
    full_name?: string;
    phone?: string;
    role?: string;
    is_active?: boolean;
  };
  headline: string;
  phone?: string | null;
  current_title?: string | null;
  years_experience?: number | null;
  skills: string[];
  role_categories: string[];
  experience_level: string;
  salary_min?: number | null;
  salary_max?: number | null;
  work_authorization: string;
  us_state?: string | null;
  remote_preference?: string | null;
  preferred_work_type?: string | null;
  availability_status: string;
  privacy_visibility: string;
  github_url?: string | null;
  portfolio_url?: string | null;
  linkedin_url?: string | null;
  resume_url?: string | null;
  bio?: string | null;
  profile_completeness?: number;
  open_to_matching?: boolean;
  profile_complete?: boolean;
  source?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface RecommendedExternalJobSourceAttribution {
  name?: string;
  provider_code?: string;
  attribution_name?: string;
  attribution_url?: string;
}

export interface RecommendedExternalJob {
  id: string;
  external_job_id: string;
  job_title: string;
  company_name: string;
  company_website?: string | null;
  location?: string | null;
  country?: string;
  state?: string | null;
  city?: string | null;
  remote_type?: string;
  employment_type?: string | null;
  salary_min?: string | number | null;
  salary_max?: string | number | null;
  salary_currency?: string;
  tech_stack?: string[];
  source_name?: string;
  source_attribution?: RecommendedExternalJobSourceAttribution | null;
  posted_at?: string | null;
  expires_at?: string | null;
  original_job_url?: string;
  source_job_url?: string | null;
  application_url?: string | null;
}

export interface CandidateExternalRecommendation {
  recommendation_id: string;
  final_score: number;
  semantic_score: number;
  skill_score: number;
  experience_score: number;
  matched_skills: string[];
  match_reason?: string | null;
  calculated_at?: string;
  external_job: RecommendedExternalJob;
}

export interface CandidateExternalRecommendationsSummary {
  total_qualified: number;
  current_page_count: number;
  highest_match_score: number;
}

export interface CandidateExternalRecommendationsResponse {
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  summary: CandidateExternalRecommendationsSummary;
  results: CandidateExternalRecommendation[];
}

export interface CandidateExternalRecommendationsParams {
  page?: number;
  page_size?: number;
  provider?: string;
  remote_type?: string;
  search?: string;
  ordering?: string;
}

export interface CandidateProfileInput {
  headline: string;
  phone?: string;
  currentTitle?: string;
  yearsExperience?: number;
  skills: string | string[];
  roleCategories: string[];
  experienceLevel: string;
  salaryMin?: number;
  salaryMax?: number;
  workAuthorization: string;
  usState?: string;
  preferredWorkType: string;
  availabilityStatus: string;
  privacyVisibility: string;
  githubUrl?: string;
  portfolioUrl?: string;
  linkedinUrl?: string;
  resumeUrl?: string;
  bio?: string;
}

export const candidatesApi = {
  /**
   * Get public talent showcase candidates
   */
  async getPublicShowcase(
    limit: number = 6,
    options?: RequestOptions,
  ): Promise<DjangoCandidateProfile[]> {
    return djangoApi.get<DjangoCandidateProfile[]>("/api/v1/candidates/public-showcase/", {
      ...options,
      params: { limit },
    });
  },

  /**
   * Get current candidate profile
   */
  async getMyProfile(options?: RequestOptions): Promise<DjangoCandidateProfile> {
    return djangoApi.get<DjangoCandidateProfile>("/api/v1/candidates/me/", options);
  },

  /**
   * Create or update candidate profile
   */
  async saveMyProfile(
    data: CandidateProfileInput,
    options?: RequestOptions,
  ): Promise<{
    ok: boolean;
    candidateProfileId: string;
    profileCompleteness: number;
    profileComplete: boolean;
    profile: DjangoCandidateProfile;
  }> {
    const payload = {
      headline: data.headline,
      phone: data.phone,
      current_title: data.currentTitle,
      years_experience: data.yearsExperience,
      skills: Array.isArray(data.skills) ? data.skills : [data.skills],
      role_categories: data.roleCategories,
      experience_level: data.experienceLevel,
      salary_min: data.salaryMin,
      salary_max: data.salaryMax,
      work_authorization: data.workAuthorization,
      us_state: data.usState,
      remote_preference: data.preferredWorkType === "remote" ? "remote" : data.preferredWorkType,
      preferred_work_type: data.preferredWorkType,
      availability_status: data.availabilityStatus,
      privacy_visibility: data.privacyVisibility,
      github_url: data.githubUrl,
      portfolio_url: data.portfolioUrl,
      linkedin_url: data.linkedinUrl,
      resume_url: data.resumeUrl,
      bio: data.bio,
    };

    return djangoApi.post<{
      ok: boolean;
      candidateProfileId: string;
      profileCompleteness: number;
      profileComplete: boolean;
      profile: DjangoCandidateProfile;
    }>("/api/v1/candidates/me/", payload, options);
  },

  /**
   * Upload resume to private storage via Django
   */
  async uploadResume(
    file: File,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; downloadUrl: string; resumePath: string }> {
    const formData = new FormData();
    formData.append("file", file);

    return djangoApi.post<{ ok: boolean; downloadUrl: string; resumePath: string }>(
      "/api/v1/candidates/me/resume/",
      formData,
      options,
    );
  },

  /**
   * Get presigned resume download URL
   */
  async getResumeDownloadUrl(
    options?: RequestOptions,
  ): Promise<{ ok: boolean; downloadUrl: string; resumePath: string }> {
    return djangoApi.get<{ ok: boolean; downloadUrl: string; resumePath: string }>(
      "/api/v1/candidates/me/resume/",
      options,
    );
  },

  /**
   * Admin: List candidates with relational filtering and search
   */
  async listAdminCandidates(
    params?: {
      q?: string;
      complete?: string;
      availability?: string;
      experience?: string;
      work_auth?: string;
      matching?: string;
      resume?: string;
      source?: string;
      limit?: number;
      offset?: number;
    },
    options?: RequestOptions,
  ): Promise<{
    candidates: any[];
    totalCount: number;
    completeCount: number;
    activeCount: number;
    count: number;
  }> {
    return djangoApi.get("/api/v1/admin/candidates/", {
      ...options,
      params,
    });
  },

  /**
   * Admin: Create a candidate account and profile
   */
  async createAdminCandidate(
    data: any,
    options?: RequestOptions,
  ): Promise<{
    ok: boolean;
    candidateProfileId: string;
    userId: string;
    matchesCreated: number;
  }> {
    return djangoApi.post("/api/v1/admin/candidates/", data, options);
  },

  /**
   * Admin: Bulk import candidates
   */
  async importAdminCandidates(
    payload: FormData | { rows: any[] },
    options?: RequestOptions,
  ): Promise<{
    ok: boolean;
    totalRows: number;
    created: number;
    failed: number;
    totalMatches: number;
    results: any[];
  }> {
    return djangoApi.post("/api/v1/admin/candidates/import/", payload, options);
  },

  /**
   * Admin: Get single candidate profile by ID
   */
  async getAdminCandidate(
    candidateId: string,
    options?: RequestOptions,
  ): Promise<DjangoCandidateProfile> {
    return djangoApi.get<DjangoCandidateProfile>(`/api/v1/candidates/${candidateId}/`, options);
  },

  /**
   * Admin: Get presigned resume download URL for candidate ID
   */
  async getAdminCandidateResume(
    candidateId: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; downloadUrl: string; resumePath: string }> {
    return djangoApi.get(`/api/v1/candidates/${candidateId}/resume/`, options);
  },

  /**
   * Admin: Upload resume for candidate ID
   */
  async uploadAdminCandidateResume(
    candidateId: string,
    file: File,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; downloadUrl: string; resumePath: string }> {
    const formData = new FormData();
    formData.append("file", file);
    return djangoApi.post(`/api/v1/candidates/${candidateId}/resume/`, formData, options);
  },

  /**
   * Admin: Activate candidate account
   */
  async activateAdminCandidate(
    candidateId: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; message: string; is_active: boolean; candidateId: string; userId: string }> {
    return djangoApi.post(`/api/v1/admin/candidates/${candidateId}/activate/`, {}, options);
  },

  /**
   * Admin: Deactivate candidate account
   */
  async deactivateAdminCandidate(
    candidateId: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; message: string; is_active: boolean; candidateId: string; userId: string }> {
    return djangoApi.post(`/api/v1/admin/candidates/${candidateId}/deactivate/`, {}, options);
  },

  /**
   * Admin: Permanently delete candidate account
   */
  async deleteAdminCandidate(
    candidateId: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; message: string; candidateId: string; userId: string }> {
    return djangoApi.delete(`/api/v1/admin/candidates/${candidateId}/delete/`, options);
  },

  /**
   * Candidate: Get AI recommended external jobs (score >= 70%)
   */
  async getExternalRecommendations(
    params?: CandidateExternalRecommendationsParams,
    options?: RequestOptions,
  ): Promise<CandidateExternalRecommendationsResponse> {
    return djangoApi.get<CandidateExternalRecommendationsResponse>(
      "/api/v1/candidates/external-recommendations/",
      {
        ...options,
        params: params as Record<string, string | number | boolean | undefined>,
      },
    );
  },

  /**
   * Candidate: Submit quality feedback or report an issue on an external job recommendation (Phase 6Z.12B)
   */
  async submitExternalRecommendationFeedback(
    data: {
      recommendation_id: string;
      reason: string;
      comments?: string;
    },
    options?: RequestOptions,
  ): Promise<{ success: boolean; message: string; feedback_id: string; reason: string; created: boolean }> {
    return djangoApi.post(
      "/api/v1/candidates/external-recommendations/feedback/",
      data,
      options,
    );
  },
};