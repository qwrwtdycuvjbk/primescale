/**
 * Job Leads API Module for Django REST Framework.
 * Phase 17 — Job Leads API Integration.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoJobLead {
  id: string;
  title: string;
  company: string;
  companyWebsite?: string | null;
  applyUrl?: string | null;
  publisher?: string | null;
  postedAt?: string | null;
  country?: string | null;
  location?: string | null;
  employmentType?: string | null;
  isRemote: boolean;
  descriptionPreview?: string | null;
  sourceLocale?: string | null;
  created_at?: string;
}

export interface JobLeadSearchParams {
  query?: string;
  country?: string;
}

export const jobLeadsApi = {
  /**
   * List or search job leads (Admin only)
   */
  async listLeads(
    params?: JobLeadSearchParams,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; count: number; leads: DjangoJobLead[] }> {
    return djangoApi.get<{ ok: boolean; count: number; leads: DjangoJobLead[] }>(
      "/api/v1/job-leads/",
      {
        ...options,
        params: params as Record<string, string | number | boolean | undefined>,
      },
    );
  },

  /**
   * Save a job lead (Admin only)
   */
  async saveLead(
    leadData: Partial<DjangoJobLead>,
    options?: RequestOptions,
  ): Promise<DjangoJobLead> {
    return djangoApi.post<DjangoJobLead>("/api/v1/job-leads/", leadData, options);
  },

  /**
   * Submit an open role (Public lead generation)
   */
  async submitRole(
    roleData: Record<string, unknown>,
    options?: RequestOptions,
  ): Promise<{ success: boolean; id: string; message: string }> {
    return djangoApi.post<{ success: boolean; id: string; message: string }>(
      "/api/v1/role-submissions/",
      roleData,
      options,
    );
  },
};
