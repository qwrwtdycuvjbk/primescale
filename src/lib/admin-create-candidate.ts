import { randomBytes } from "crypto";
import { parseSkills } from "@/lib/matching";
import { runMatchingForCandidate } from "@/lib/match-runner";
import { calculateProfileCompleteness } from "@/lib/profile-completeness";
import { getServiceClient } from "@/lib/supabase/service";
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

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function formatCandidateDbError(message: string) {
  if (message.includes("source") && message.includes("schema cache")) {
    return "Database missing candidate source column. Run supabase/candidate-source.sql in the Supabase SQL Editor, then try again.";
  }
  return message;
}

export async function createAdminCandidate(
  input: AdminCreateCandidateInput,
): Promise<AdminCreateCandidateResult> {
  const supabase = getServiceClient();
  if (!supabase) {
    return { ok: false, error: "Service unavailable", status: 503 };
  }

  const fullName = input.fullName.trim();
  const email = normalizeEmail(input.email);
  const skills = parseSkills(input.skills);

  if (!fullName) {
    return { ok: false, error: "Full name is required", status: 400 };
  }

  if (!email || !email.includes("@")) {
    return { ok: false, error: "A valid email is required", status: 400 };
  }

  if (!input.headline.trim()) {
    return { ok: false, error: "Headline is required", status: 400 };
  }

  if (skills.length === 0) {
    return { ok: false, error: "Add at least one skill", status: 400 };
  }

  if (input.roleCategories.length === 0) {
    return { ok: false, error: "Select at least one role category", status: 400 };
  }

  const { data: existingProfile } = await supabase
    .from("profiles")
    .select("id, role, email")
    .eq("email", email)
    .maybeSingle();

  if (existingProfile) {
    return {
      ok: false,
      error: `A ${existingProfile.role} account already exists for this email`,
      status: 409,
    };
  }

  const password = randomBytes(24).toString("base64url");
  const { data: authData, error: authError } = await supabase.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: {
      full_name: fullName,
      role: "candidate",
    },
  });

  if (authError || !authData.user) {
    return {
      ok: false,
      error: authError?.message ?? "Could not create user account",
      status: 500,
    };
  }

  const userId = authData.user.id;

  const profileInput = {
    headline: input.headline.trim(),
    phone: input.phone?.trim() || undefined,
    currentTitle: input.currentTitle?.trim(),
    yearsExperience: input.yearsExperience,
    skills: input.skills,
    roleCategories: input.roleCategories,
    experienceLevel: input.experienceLevel,
    salaryMin: input.salaryMin,
    salaryMax: input.salaryMax,
    workAuthorization: input.workAuthorization,
    usState: input.usState,
    preferredWorkType: input.preferredWorkType,
    availabilityStatus: input.availabilityStatus,
    privacyVisibility: input.privacyVisibility,
    bio: input.bio,
    githubUrl: input.githubUrl,
    portfolioUrl: input.portfolioUrl,
    linkedinUrl: input.linkedinUrl,
    resumeUrl: input.resumeUrl,
  };

  const completeness = calculateProfileCompleteness(profileInput);
  const hasRequiredFields =
    Boolean(input.headline.trim()) &&
    Boolean(input.currentTitle?.trim()) &&
    skills.length > 0 &&
    input.roleCategories.length > 0;

  const isComplete = hasRequiredFields;

  const { error: profileError } = await supabase
    .from("profiles")
    .update({
      full_name: fullName,
      phone: input.phone?.trim() || null,
      role: "candidate",
      updated_at: new Date().toISOString(),
    })
    .eq("id", userId);

  if (profileError) {
    await supabase.auth.admin.deleteUser(userId);
    return { ok: false, error: profileError.message, status: 500 };
  }

  const source = input.source ?? "people_prime";

  const { data: candidateProfile, error: candidateError } = await supabase
    .from("candidate_profiles")
    .insert({
      user_id: userId,
      headline: input.headline.trim(),
      phone: input.phone?.trim() || null,
      current_title: input.currentTitle?.trim() || null,
      years_experience: input.yearsExperience ?? null,
      skills,
      role_categories: input.roleCategories,
      experience_level: input.experienceLevel,
      salary_min: input.salaryMin ?? null,
      salary_max: input.salaryMax ?? null,
      work_authorization: input.workAuthorization,
      us_state: input.usState,
      remote_preference: input.preferredWorkType === "remote" ? "remote" : input.preferredWorkType,
      preferred_work_type: input.preferredWorkType,
      availability_status: input.availabilityStatus,
      privacy_visibility: input.privacyVisibility,
      github_url: input.githubUrl?.trim() || null,
      portfolio_url: input.portfolioUrl?.trim() || null,
      linkedin_url: input.linkedinUrl?.trim() || null,
      resume_url: input.resumeUrl?.trim() || null,
      bio: input.bio?.trim() || null,
      profile_completeness: completeness,
      open_to_matching: input.availabilityStatus !== "not_looking",
      profile_complete: isComplete,
      source,
      updated_at: new Date().toISOString(),
    })
    .select("id")
    .single();

  if (candidateError || !candidateProfile) {
    await supabase.auth.admin.deleteUser(userId);
    return {
      ok: false,
      error: formatCandidateDbError(
        candidateError?.message ?? "Could not create candidate profile",
      ),
      status: 500,
    };
  }

  const matchResult =
    isComplete && input.availabilityStatus !== "not_looking"
      ? await runMatchingForCandidate(candidateProfile.id)
      : { matched: 0 };

  return {
    ok: true,
    candidateProfileId: candidateProfile.id,
    userId,
    matchesCreated: matchResult.matched,
  };
}

export async function uploadAdminCandidateResume(
  candidateProfileId: string,
  file: File,
): Promise<{ ok: true; resumeUrl: string } | { ok: false; error: string; status: number }> {
  const supabase = getServiceClient();
  if (!supabase) {
    return { ok: false, error: "Service unavailable", status: 503 };
  }

  const allowed = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  if (!allowed.includes(file.type)) {
    return { ok: false, error: "Only PDF or DOCX files are allowed", status: 400 };
  }

  const { data: candidate, error: lookupError } = await supabase
    .from("candidate_profiles")
    .select("user_id")
    .eq("id", candidateProfileId)
    .maybeSingle();

  if (lookupError || !candidate) {
    return { ok: false, error: "Candidate not found", status: 404 };
  }

  const ext = file.name.split(".").pop() ?? "pdf";
  const path = `${candidate.user_id}/resume-${Date.now()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from("resumes")
    .upload(path, file, { upsert: true });

  if (uploadError) {
    return { ok: false, error: uploadError.message, status: 500 };
  }

  const { error: updateError } = await supabase
    .from("candidate_profiles")
    .update({
      resume_url: path,
      updated_at: new Date().toISOString(),
    })
    .eq("id", candidateProfileId);

  if (updateError) {
    return { ok: false, error: updateError.message, status: 500 };
  }

  return { ok: true, resumeUrl: path };
}
