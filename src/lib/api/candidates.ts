/**
 * Candidates API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoCandidateProfile {
  id: string;
  user_id?: string;
  user_email?: string;
  user_full_name?: string;
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
  profile_completeness: number;
  open_to_matching: boolean;
  profile_complete: boolean;
  created_at?: string;
  updated_at?: string;
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
};

