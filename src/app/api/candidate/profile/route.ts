import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { parseSkills } from "@/lib/matching";
import { runMatchingForCandidate } from "@/lib/match-runner";
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

  const profileRow = {
    user_id: user.id,
    headline: body.headline,
    skills,
    role_categories: body.roleCategories,
    experience_level: body.experienceLevel,
    salary_min: body.salaryMin ?? null,
    salary_max: body.salaryMax ?? null,
    work_authorization: body.workAuthorization,
    us_state: body.usState,
    remote_preference: "remote",
    bio: body.bio ?? null,
    open_to_matching: true,
    profile_complete: true,
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

  const matchResult = await runMatchingForCandidate(candidateProfileId);

  return NextResponse.json({
    ok: true,
    candidateProfileId,
    matchesCreated: matchResult.matched,
  });
}
