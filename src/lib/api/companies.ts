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

export interface DjangoEmployerMember {
  id: string;
  user_id?: string;
  email?: string;
  full_name?: string;
  role?: string;
  created_at?: string;
}

export interface DjangoEmployerProfile {
  id: string;
  company?: DjangoCompany;
  role?: string;
  full_name?: string;
  email?: string;
  company_name?: string;
  company_website?: string;
  company_location?: string;
  company_size?: string;
  industry?: string;
  bio?: string;
  created_at?: string;
  updated_at?: string;
}

export interface DjangoAdminEmployer {
  id: string;
  name: string;
  website?: string | null;
  location?: string | null;
  industry?: string | null;
  company_size?: string | null;
  created_at: string;
  jobs_count: number;
  members_count: number;
  primary_contact_name: string;
  primary_contact_email: string;
  primary_contact_active: boolean;
  is_active: boolean;
  profile_complete: boolean;
}

export interface DjangoAdminEmployerDetail extends DjangoAdminEmployer {
  description?: string | null;
  logo_url?: string | null;
  members: Array<{
    id: string;
    user_id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
    created_at: string;
  }>;
  jobs: Array<{
    id: string;
    title: string;
    location: string;
    work_location_type: string;
    employment_type: string;
    status: string;
    created_at: string;
    applications_count?: number;
    matches_count?: number;
  }>;
}

export const companiesApi = {
  /**
   * Get authenticated employer's company
   */
  async getMyCompany(options?: RequestOptions): Promise<DjangoCompany> {
    return djangoApi.get<DjangoCompany>("/api/v1/companies/me/", options);
  },

  /**
   * Alias for getMyCompany / profile
   */
  async getMyProfile(options?: RequestOptions): Promise<DjangoEmployerProfile> {
    return djangoApi.get<DjangoEmployerProfile>("/api/v1/companies/me/", options);
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

  /**
   * Admin: List all employers / companies (read-only)
   */
  async listAdminEmployers(
    params?: {
      q?: string;
      status?: string;
      industry?: string;
      limit?: number;
      offset?: number;
    },
    options?: RequestOptions,
  ): Promise<{
    employers: DjangoAdminEmployer[];
    totalCount: number;
    activeCount: number;
    count: number;
  }> {
    return djangoApi.get("/api/v1/admin/employers/", {
      ...options,
      params,
    });
  },

  /**
   * Admin: Get single employer / company detail by ID (read-only)
   */
  async getAdminEmployer(
    employerId: string,
    options?: RequestOptions,
  ): Promise<DjangoAdminEmployerDetail> {
    return djangoApi.get<DjangoAdminEmployerDetail>(`/api/v1/admin/employers/${employerId}/`, options);
  },
};
