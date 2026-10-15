/**
 * Jobs API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoJob {
  id: string;
  company?: string;
  company_id?: string;
  companies?: {
    id: string;
    name: string;
    website?: string;
    logo_url?: string;
    hq_city?: string;
    country?: string;
  };
  company_details?: {
    id: string;
    name: string;
    website?: string;
    logo_url?: string;
    hq_city?: string;
    country?: string;
  };
  posted_by?: string;
  posted_by_email?: string;
  posted_by_full_name?: string;
  title: string;
  description: string;
  role_type: string;
  experience_level: string;
  tech_stack: string[];
  salary_range: string;
  work_type: string;
  visa_requirements?: string;
  status: "draft" | "active" | "paused" | "closed" | "archived";
  expires_at?: string | null;
  jd_quality_score?: number | null;
  jd_quality_feedback?: string | null;
  featured?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface JobFilterParams {
  q?: string;
  experience_level?: string;
  role_type?: string;
  work_type?: string;
  status?: string;
  company_id?: string;
  view?: "my_company" | "all";
}

export interface CreateJobInput {
  company_id?: string;
  title: string;
  description: string;
  role_type: string;
  experience_level: string;
  tech_stack: string[];
  salary_range: string;
  work_type?: string;
  visa_requirements?: string;
  publish?: boolean;
  status?: string;
  jd_quality_score?: number | null;
  jd_quality_feedback?: string | null;
  featured?: boolean;
}

export interface UpdateJobInput extends Partial<CreateJobInput> {
  status?: "draft" | "active" | "paused" | "closed" | "archived";
}

export interface EmployerPublicJob {
  id: string;
  title: string;
  company_name: string;
  company_logo?: string | null;
  company_website?: string | null;
  location: string;
  work_type: string;
  role_type: string;
  experience_level: string;
  salary_range?: string | null;
  tech_stack: string[];
  description: string;
  description_summary: string;
  source_name: string;
  featured: boolean;
  expires_at?: string | null;
  created_at: string;
}

export interface PaginatedEmployerJobs {
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  results: EmployerPublicJob[];
}

export interface PublicJobFilterParams {
  page?: number;
  page_size?: number;
  search?: string;
  technology?: string;
  role_type?: string;
  experience_level?: string;
  work_type?: string;
}

export const jobsApi = {
  /**
   * Fetch paginated list of public active employer-posted jobs
   */
  async listPublicJobs(
    params?: PublicJobFilterParams,
    options?: RequestOptions,
  ): Promise<PaginatedEmployerJobs> {
    return djangoApi.get<PaginatedEmployerJobs>("/api/v1/jobs/public/", {
      ...options,
      params: params as Record<string, string | number | boolean | undefined>,
    });
  },

  /**
   * Retrieve a single public active employer job by UUID
   */
  async getPublicJob(id: string, options?: RequestOptions): Promise<EmployerPublicJob> {
    return djangoApi.get<EmployerPublicJob>(`/api/v1/jobs/public/${id}/`, options);
  },

  /**
   * List jobs with filters
   */
  async listJobs(params?: JobFilterParams, options?: RequestOptions): Promise<DjangoJob[]> {
    return djangoApi.get<DjangoJob[]>("/api/v1/jobs/", {
      ...options,
      params: params as Record<string, string | number | boolean | undefined>,
    });
  },

  /**
   * List authenticated employer's company jobs
   */
  async getMyJobs(options?: RequestOptions): Promise<DjangoJob[]> {
    return djangoApi.get<DjangoJob[]>("/api/v1/jobs/", {
      ...options,
      params: { view: "my_company" },
    });
  },


  /**
   * Retrieve a single job by UUID
   */
  async getJob(id: string, options?: RequestOptions): Promise<DjangoJob> {
    return djangoApi.get<DjangoJob>(`/api/v1/jobs/${id}/`, options);
  },

  /**
   * Create a job post
   */
  async createJob(
    data: CreateJobInput,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; jobId: string; status: string; job: DjangoJob }> {
    return djangoApi.post<{ ok: boolean; jobId: string; status: string; job: DjangoJob }>(
      "/api/v1/jobs/",
      data,
      options,
    );
  },

  /**
   * Update a job post
   */
  async updateJob(
    id: string,
    data: UpdateJobInput,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; job: DjangoJob }> {
    return djangoApi.patch<{ ok: boolean; job: DjangoJob }>(
      `/api/v1/jobs/${id}/`,
      data,
      options,
    );
  },

  /**
   * Duplicate a job post as draft
   */
  async duplicateJob(
    id: string,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; jobId: string; job: DjangoJob }> {
    return djangoApi.post<{ ok: boolean; jobId: string; job: DjangoJob }>(
      `/api/v1/jobs/${id}/duplicate/`,
      {},
      options,
    );
  },

  /**
   * Delete a job
   */
  async deleteJob(id: string, options?: RequestOptions): Promise<void> {
    return djangoApi.delete<void>(`/api/v1/jobs/${id}/`, options);
  },
};
