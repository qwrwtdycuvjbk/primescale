import type { CandidateProfileInput } from "@/lib/types";

export function calculateProfileCompleteness(
  data: Partial<CandidateProfileInput>,
): number {
  const checks = [
    Boolean(data.headline?.trim()),
    Boolean(data.phone?.trim()),
    Boolean(data.currentTitle?.trim()),
    data.yearsExperience !== undefined && data.yearsExperience >= 0,
    Boolean(data.skills?.trim()),
    (data.roleCategories?.length ?? 0) > 0,
    Boolean(data.experienceLevel),
    Boolean(data.workAuthorization),
    Boolean(data.usState),
    data.salaryMin !== undefined || data.salaryMax !== undefined,
    Boolean(data.bio?.trim()),
    Boolean(data.resumeUrl),
    Boolean(data.githubUrl?.trim() || data.portfolioUrl?.trim()),
    Boolean(data.availabilityStatus),
    Boolean(data.preferredWorkType),
  ];

  const filled = checks.filter(Boolean).length;
  return Math.round((filled / checks.length) * 100);
}
