import { djangoApi } from "@/lib/api/client";
import { workAuthLabel as formatWorkAuthLabel } from "@/lib/constants";
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

export async function getPublicTalentShowcase(
  limit = 8,
): Promise<PublicTalentCard[]> {
  try {
    const djangoCards = await djangoApi.get<PublicTalentCard[]>(
      "/api/v1/candidates/public-showcase/",
      { params: { limit } },
    );
    if (djangoCards && Array.isArray(djangoCards)) {
      return djangoCards;
    }
  } catch (err) {
    console.error("Failed to load public talent showcase from Django:", err);
  }

  return [];
}
