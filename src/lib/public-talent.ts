import { workAuthLabel as formatWorkAuthLabel } from "@/lib/constants";
import { getServiceClient } from "@/lib/supabase/service";
import type { ExperienceLevel } from "@/lib/types";

export type PublicTalentCard = {
  id: string;
  displayName: string;
  initials: string;
  title: string;
  bioSnippet?: string;
  experienceLevel?: ExperienceLevel;
  experienceLevelLabel?: string;
  yearsExperience?: number;
  skills: string[];
  hiddenSkillCount: number;
  roleCategories: string[];
  workAuthorizationLabel?: string;
  location?: string;
  availabilityLabel: string;
  salaryRange?: string;
};

function formatDisplayName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "Engineer";
  if (parts.length === 1) return parts[0];
  return `${parts[0]} ${parts[parts.length - 1][0]}.`;
}

function initialsFromName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "PS";
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatSalaryRange(min?: number | null, max?: number | null): string | undefined {
  if (!min && !max) return undefined;
  const fmt = (value: number) =>
    value >= 1000 ? `$${Math.round(value / 1000)}k` : `$${value}`;
  if (min && max) return `${fmt(min)}–${fmt(max)}`;
  if (min) return `${fmt(min)}+`;
  if (max) return `Up to ${fmt(max)}`;
  return undefined;
}

function availabilityLabel(value?: string | null): string {
  switch (value) {
    case "actively_looking":
      return "Actively looking";
    case "open":
      return "Open to roles";
    default:
      return "Available";
  }
}

function experienceLevelLabel(value?: string | null): string | undefined {
  switch (value) {
    case "junior":
      return "Junior";
    case "mid":
      return "Mid-level";
    case "senior":
      return "Senior";
    case "lead":
      return "Lead / Staff";
    default:
      return undefined;
  }
}

function formatLocation(value?: string | null): string | undefined {
  if (!value) return undefined;
  if (value === "Remote (US)") return "Remote";
  return value;
}

function truncateBio(value?: string | null, maxLength = 180): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  if (trimmed.length <= maxLength) return trimmed;
  return `${trimmed.slice(0, maxLength).trimEnd()}…`;
}

export async function getPublicTalentShowcase(
  limit = 8,
): Promise<PublicTalentCard[]> {
  const supabase = getServiceClient();
  if (!supabase) return [];

  const { data, error } = await supabase
    .from("candidate_profiles")
    .select(
      `
      id,
      headline,
      bio,
      current_title,
      years_experience,
      skills,
      role_categories,
      experience_level,
      salary_min,
      salary_max,
      work_authorization,
      us_state,
      availability_status,
      profiles:user_id ( full_name )
    `,
    )
    .eq("privacy_visibility", "public")
    .eq("profile_complete", true)
    .eq("open_to_matching", true)
    .in("availability_status", ["actively_looking", "open"])
    .order("updated_at", { ascending: false })
    .limit(limit);

  if (error || !data?.length) return [];

  return data.map((row) => {
    const profileRaw = row.profiles;
    const profile = Array.isArray(profileRaw) ? profileRaw[0] : profileRaw;
    const fullName = profile?.full_name?.trim() || "Engineer";
    const title =
      row.current_title?.trim() ||
      row.headline?.trim() ||
      experienceLevelLabel(row.experience_level) ||
      "Remote engineer";
    const allSkills = (row.skills as string[] | null) ?? [];
    const bioSource = row.bio?.trim() || row.headline?.trim();

    return {
      id: row.id,
      displayName: formatDisplayName(fullName),
      initials: initialsFromName(fullName),
      title,
      bioSnippet: truncateBio(bioSource),
      experienceLevel: row.experience_level as ExperienceLevel | undefined,
      experienceLevelLabel: experienceLevelLabel(row.experience_level),
      yearsExperience: row.years_experience ?? undefined,
      skills: allSkills.slice(0, 3),
      hiddenSkillCount: Math.max(0, allSkills.length - 3),
      roleCategories: (row.role_categories as string[] | null)?.slice(0, 2) ?? [],
      workAuthorizationLabel: (() => {
        const label = formatWorkAuthLabel(row.work_authorization);
        return label === "—" ? undefined : label;
      })(),
      location: formatLocation(row.us_state),
      availabilityLabel: availabilityLabel(row.availability_status),
      salaryRange: formatSalaryRange(row.salary_min, row.salary_max),
    };
  });
}
