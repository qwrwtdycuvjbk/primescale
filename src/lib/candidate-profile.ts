import type { CandidateProfileInput } from "@/lib/types";

export function mapCandidateRowToInput(
  row: Record<string, unknown>,
  profilePhone?: string,
): Partial<CandidateProfileInput> {
  return {
    headline: (row.headline as string) ?? "",
    phone: (row.phone as string) ?? profilePhone ?? "",
    currentTitle: (row.current_title as string) ?? "",
    yearsExperience: (row.years_experience as number) ?? undefined,
    skills: Array.isArray(row.skills) ? row.skills.join(", ") : "",
    roleCategories: (row.role_categories as string[]) ?? [],
    experienceLevel: (row.experience_level as CandidateProfileInput["experienceLevel"]) ?? "mid",
    salaryMin: (row.salary_min as number) ?? undefined,
    salaryMax: (row.salary_max as number) ?? undefined,
    workAuthorization: (row.work_authorization as string) ?? "us_citizen",
    usState: (row.us_state as string) ?? "Remote (US)",
    preferredWorkType:
      (row.preferred_work_type as CandidateProfileInput["preferredWorkType"]) ?? "remote",
    availabilityStatus:
      (row.availability_status as CandidateProfileInput["availabilityStatus"]) ??
      "actively_looking",
    privacyVisibility:
      (row.privacy_visibility as CandidateProfileInput["privacyVisibility"]) ??
      "employers_only",
    bio: (row.bio as string) ?? "",
    githubUrl: (row.github_url as string) ?? "",
    portfolioUrl: (row.portfolio_url as string) ?? "",
    linkedinUrl: (row.linkedin_url as string) ?? "",
    resumeUrl: (row.resume_url as string) ?? "",
  };
}

export function isCandidateProfileComplete(
  row: { profile_complete?: boolean; resume_url?: string | null } | null,
): boolean {
  if (!row) return false;
  return Boolean(row.profile_complete && row.resume_url?.trim());
}
