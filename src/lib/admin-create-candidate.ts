import { candidatesApi } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type {
  AvailabilityStatus,
  CandidateSource,
  ExperienceLevel,
  PreferredWorkType,
  PrivacyVisibility,
} from "@/lib/types";

export type AdminCreateCandidateInput = {
  fullName: string;
  email: string;
  phone?: string;
  headline: string;
  currentTitle?: string;
  yearsExperience?: number;
  skills: string;
  roleCategories: string[];
  experienceLevel: ExperienceLevel;
  salaryMin?: number;
  salaryMax?: number;
  workAuthorization: string;
  usState: string;
  preferredWorkType: PreferredWorkType;
  availabilityStatus: AvailabilityStatus;
  privacyVisibility: PrivacyVisibility;
  bio?: string;
  githubUrl?: string;
  portfolioUrl?: string;
  linkedinUrl?: string;
  resumeUrl?: string;
  source?: CandidateSource;
};

export type AdminCreateCandidateResult =
  | { ok: true; candidateProfileId: string; userId: string; matchesCreated: number }
  | { ok: false; error: string; status: number };

export async function createAdminCandidate(
  input: AdminCreateCandidateInput,
): Promise<AdminCreateCandidateResult> {
  try {
    const token = await getAccessToken();
    const res = await candidatesApi.createAdminCandidate(input, { token });
    if (res && res.ok) {
      return {
        ok: true,
        candidateProfileId: res.candidateProfileId,
        userId: res.userId,
        matchesCreated: res.matchesCreated,
      };
    }
    return {
      ok: false,
      error: "Failed to create candidate",
      status: 400,
    };
  } catch (err: any) {
    return {
      ok: false,
      error: err?.message || err?.error || "Failed to create candidate",
      status: err?.status || 400,
    };
  }
}

export async function uploadAdminCandidateResume(
  candidateProfileId: string,
  file: File,
): Promise<{ ok: true; resumeUrl: string } | { ok: false; error: string; status: number }> {
  try {
    const token = await getAccessToken();
    const res = await candidatesApi.uploadAdminCandidateResume(candidateProfileId, file, { token });
    if (res && res.ok) {
      return { ok: true, resumeUrl: res.downloadUrl || res.resumePath };
    }
    return { ok: false, error: "Failed to upload resume", status: 400 };
  } catch (err: any) {
    return {
      ok: false,
      error: err?.message || err?.error || "Upload failed",
      status: err?.status || 400,
    };
  }
}
