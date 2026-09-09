/**
 * Companies API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";

export interface DjangoCompany {
  id: string;
  name: string;
  website?: string | null;
  size?: string | null;
  description?: string | null;
  hq_city?: string | null;
  industry?: string | null;
  remote_culture_statement?: string | null;
  logo_url?: string | null;
  country?: string;
  domain_verified?: boolean;
  badge_remote_first?: boolean;
  badge_visa_sponsor?: boolean;
  profile_complete?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface CompanyInput {
  name: string;
  website?: string;
  size?: string;
  description?: string;
  hqCity?: string;
  industry?: string;
  remoteCultureStatement?: string;
  logoUrl?: string;
  workEmail?: string;
}

export const companiesApi = {
  /**
   * Get authenticated employer's company
   */
  async getMyCompany(options?: RequestOptions): Promise<DjangoCompany> {
    return djangoApi.get<DjangoCompany>("/api/v1/companies/me/", options);
  },

  /**
   * Create or update authenticated employer's company
   */
  async saveMyCompany(
    data: CompanyInput,
    options?: RequestOptions,
  ): Promise<{
    ok: boolean;
    companyId: string;
    domainVerified: boolean;
    profileComplete: boolean;
    company: DjangoCompany;
  }> {
    // Map camelCase to snake_case for Django serializer
    const payload = {
      name: data.name,
      website: data.website,
      size: data.size,
      description: data.description,
      hq_city: data.hqCity,
      industry: data.industry,
      remote_culture_statement: data.remoteCultureStatement,
      logo_url: data.logoUrl,
      work_email: data.workEmail,
    };

    return djangoApi.post<{
      ok: boolean;
      companyId: string;
      domainVerified: boolean;
      profileComplete: boolean;
      company: DjangoCompany;
    }>("/api/v1/companies/me/", payload, options);
  },

  /**
   * Upload company logo to S3 / media storage via Django
   */
  async uploadLogo(
    file: File,
    options?: RequestOptions,
  ): Promise<{ ok: boolean; url: string; logoPath: string }> {
    const formData = new FormData();
    formData.append("file", file);

    return djangoApi.post<{ ok: boolean; url: string; logoPath: string }>(
      "/api/v1/companies/me/logo/",
      formData,
      options,
    );
  },

  /**
   * Get company by ID (public / member / owner view)
   */
  async getCompanyById(
    id: string,
    options?: RequestOptions,
  ): Promise<DjangoCompany> {
    return djangoApi.get<DjangoCompany>(`/api/v1/companies/${id}/`, options);
  },

  /**
   * List all companies (for dropdowns and listings)
   */
  async listCompanies(
    options?: RequestOptions,
  ): Promise<DjangoCompany[]> {
    return djangoApi.get<DjangoCompany[]>("/api/v1/companies/", options);
  },

  /**
   * Get company members
   */
  async getCompanyMembers(
    companyId: string,
    options?: RequestOptions,
  ): Promise<
    Array<{
      id: string;
      user_id: string;
      user_email: string;
      user_full_name?: string;
      member_role: string;
      created_at: string;
    }>
  > {
    return djangoApi.get(
      `/api/v1/companies/${companyId}/members/`,
      options,
    );
  },
};


