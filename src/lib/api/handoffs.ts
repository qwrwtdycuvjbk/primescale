/**
 * Handoffs API Module for Django REST Framework.
 */

import { djangoApi, RequestOptions } from "./client";
import type { DjangoMatch } from "./matching";

export interface DjangoHandoffEmployer {
  id: string;
  full_name: string;
  email: string;
  phone?: string | null;
}

export interface DjangoHandoff {
  id: string;
  match_id?: string;
  match: DjangoMatch;
  matches?: DjangoMatch;
  employer?: DjangoHandoffEmployer | null;
  status: "pending" | "contacted" | "intro_made" | "closed";
  notes?: string | null;
  notified_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface HandoffFilterParams {
  status?: string;
}

export const handoffsApi = {
  /**
   * List handoffs filtered by role and optional status
   */
  async listHandoffs(status?: string, options?: RequestOptions): Promise<DjangoHandoff[]> {
    return djangoApi.get<DjangoHandoff[]>("/api/v1/handoffs/", {
      ...options,
      params: status && status !== "all" ? { status } : undefined,
    });
  },

  /**
   * Get single handoff detail
   */
  async getHandoff(id: string, options?: RequestOptions): Promise<DjangoHandoff> {
    return djangoApi.get<DjangoHandoff>(`/api/v1/handoffs/${id}/`, options);
  },

  /**
   * Update handoff status & notes (admin/recruiter action)
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
