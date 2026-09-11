/**
 * External Jobs API Client Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface ExternalJobSource {
  id: string;
  name: string;
  provider_code: string;
  attribution_name: string;
  attribution_url?: string | null;
}

export interface ExternalJob {
  id: string;
  external_job_id: string;
  title: string;
  company_name: string;
  company_website?: string | null;
  description: string;
  location?: string | null;
  country: string;
  state?: string | null;
  city?: string | null;
  remote_type: "REMOTE" | "HYBRID" | "ONSITE" | "UNKNOWN";
  employment_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency: string;
  tech_stack: string[];
  original_job_url: string;
  source_job_url?: string | null;
  source_name: string;
  source_attribution?: ExternalJobSource | null;
  posted_at?: string | null;
  expires_at?: string | null;
  status: "ACTIVE" | "INACTIVE" | "EXPIRED";
  is_active: boolean;
  created_at: string;
}

export interface ExternalJobFilterParams {
  page?: number;
  page_size?: number;
  search?: string;
  source?: string;
  remote?: boolean | string;
  country?: string;
  technology?: string;
  employment_type?: string;
}

export interface PaginatedExternalJobs {
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  results: ExternalJob[];
}

export const externalJobsApi = {
  /**
   * Fetch paginated list of external aggregated jobs with optional conservative US Remote filtering
   */
  async listExternalJobs(
    params?: ExternalJobFilterParams,
    options?: RequestOptions,
  ): Promise<PaginatedExternalJobs> {
    return djangoApi.get<PaginatedExternalJobs>("/api/v1/external-jobs/", {
      ...options,
      params: params as Record<string, string | number | boolean | undefined>,
    });
  },
};
