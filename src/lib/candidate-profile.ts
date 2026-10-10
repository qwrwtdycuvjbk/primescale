import type { CandidateProfileInput } from "@/lib/types";

export function mapCandidateRowToInput(
  row: any,
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
  row: {
    profile_complete?: boolean;
    headline?: string | null;
    phone?: string | null;
    current_title?: string | null;
    currentTitle?: string | null;
    skills?: string[] | string | null;
    role_categories?: string[] | null;
    roleCategories?: string[] | null;
    resume_url?: string | null;
    resumeUrl?: string | null;
    user?: Record<string, any> | null;
    profiles?: Record<string, any> | null;
    [key: string]: any;
  } | null,
): boolean {
  if (!row) return false;

  const headline = typeof row.headline === "string" ? row.headline.trim() : "";

  const rawPhone =
    row.phone ??
    row.user?.phone ??
    row.profiles?.phone ??
    "";
  const phone = typeof rawPhone === "string" ? rawPhone.trim() : "";

  const rawTitle = row.current_title ?? row.currentTitle ?? "";
  const currentTitle = typeof rawTitle === "string" ? rawTitle.trim() : "";

  const rawResume = row.resume_url ?? row.resumeUrl ?? "";
  const resumeUrl = typeof rawResume === "string" ? rawResume.trim() : "";

  let skillsCount = 0;
  if (Array.isArray(row.skills)) {
    skillsCount = row.skills.filter((s) => typeof s === "string" && s.trim().length > 0).length;
  } else if (typeof row.skills === "string") {
    skillsCount = row.skills.split(",").filter((s) => s.trim().length > 0).length;
  }

  const rawRoleCats = row.role_categories ?? row.roleCategories;
  const roleCategoriesCount = Array.isArray(rawRoleCats)
    ? rawRoleCats.filter((c) => typeof c === "string" && c.trim().length > 0).length
    : 0;

  const hasRequiredFields =
    headline.length > 0 &&
    phone.length > 0 &&
    currentTitle.length > 0 &&
    skillsCount > 0 &&
    roleCategoriesCount > 0 &&
    resumeUrl.length > 0;

  if (row.profile_complete === false) {
    return false;
  }

  return hasRequiredFields;
}
