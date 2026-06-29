import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { parseSkills } from "@/lib/matching";
import { runMatchingForCandidate } from "@/lib/match-runner";
import { calculateProfileCompleteness } from "@/lib/profile-completeness";
import type { CandidateProfileInput } from "@/lib/types";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as CandidateProfileInput;
  const skills = parseSkills(body.skills);

  if (skills.length === 0) {
    return NextResponse.json({ error: "Add at least one skill" }, { status: 400 });
  }

  if (!body.resumeUrl?.trim()) {
    return NextResponse.json(
      { error: "Resume upload is required" },
      { status: 400 },
    );
  }

  const completeness = calculateProfileCompleteness(body);
  const hasRequiredFields =
    Boolean(body.headline?.trim()) &&
    Boolean(body.phone?.trim()) &&
    Boolean(body.currentTitle?.trim()) &&
    skills.length > 0 &&
    body.roleCategories.length > 0;

  const isComplete = hasRequiredFields && Boolean(body.resumeUrl?.trim());

  if (body.phone) {
    await supabase
      .from("profiles")
      .update({ phone: body.phone, updated_at: new Date().toISOString() })
      .eq("id", user.id);
  }

  const profileRow = {
    user_id: user.id,
    headline: body.headline,
    phone: body.phone ?? null,
    current_title: body.currentTitle ?? null,
    years_experience: body.yearsExperience ?? null,
    skills,
    role_categories: body.roleCategories,
    experience_level: body.experienceLevel,
    salary_min: body.salaryMin ?? null,
    salary_max: body.salaryMax ?? null,
    work_authorization: body.workAuthorization,
    us_state: body.usState,
    remote_preference: body.preferredWorkType === "remote" ? "remote" : body.preferredWorkType,
    preferred_work_type: body.preferredWorkType,
    availability_status: body.availabilityStatus,
    privacy_visibility: body.privacyVisibility,
    github_url: body.githubUrl || null,
    portfolio_url: body.portfolioUrl || null,
    linkedin_url: body.linkedinUrl || null,
    resume_url: body.resumeUrl || null,
    bio: body.bio ?? null,
    profile_completeness: completeness,
    open_to_matching: body.availabilityStatus !== "not_looking",
    profile_complete: isComplete,
    updated_at: new Date().toISOString(),
  };

  const { data: existing } = await supabase
    .from("candidate_profiles")
    .select("id")
    .eq("user_id", user.id)
    .maybeSingle();

  let candidateProfileId: string;

  if (existing) {
    const { data, error } = await supabase
      .from("candidate_profiles")
      .update(profileRow)
      .eq("user_id", user.id)
      .select("id")
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    candidateProfileId = data.id;
  } else {
    const { data, error } = await supabase
      .from("candidate_profiles")
      .insert(profileRow)
      .select("id")
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    candidateProfileId = data.id;
  }

  const matchResult = isComplete
    ? await runMatchingForCandidate(candidateProfileId)
    : { matched: 0 };

  return NextResponse.json({
    ok: true,
    candidateProfileId,
    profileCompleteness: completeness,
    matchesCreated: matchResult.matched,
  });
}
