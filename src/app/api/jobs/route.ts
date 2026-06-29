import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { parseSkills } from "@/lib/matching";
import { runMatchingForJob } from "@/lib/match-runner";
import type { JobInput } from "@/lib/types";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as JobInput;
  const description = body.description?.trim();

  if (!description) {
    return NextResponse.json({ error: "Description is required" }, { status: 400 });
  }

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("owner_id", user.id)
    .maybeSingle();

  if (!company) {
    return NextResponse.json(
      { error: "Complete company onboarding first" },
      { status: 400 },
    );
  }

  const techStack = parseSkills(body.techStack);
  const title = body.title?.trim() || "Remote tech role";

  const { data: job, error } = await supabase
    .from("jobs")
    .insert({
      company_id: company.id,
      posted_by: user.id,
      title,
      description,
      role_type: body.roleType,
      experience_level: body.experienceLevel,
      tech_stack: techStack,
      salary_range: body.salaryRange || null,
      work_type: "remote",
      visa_requirements: body.visaRequirements || null,
      status: "active",
    })
    .select("id")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const matchResult = await runMatchingForJob(job.id);

  return NextResponse.json({
    ok: true,
    jobId: job.id,
    matchesCreated: matchResult.matched,
  });
}
