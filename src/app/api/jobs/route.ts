import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  defaultJobExpiry,
  isValidSalaryRange,
} from "@/lib/employer";
import { parseSkills } from "@/lib/matching";
import { notifyRecruitersJobPosted } from "@/lib/job-notifications";
import { runMatchingForJob } from "@/lib/match-runner";
import type { JobInput, JobStatus } from "@/lib/types";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as JobInput & {
    publish?: boolean;
    jdQualityScore?: number;
    jdQualityFeedback?: string;
  };

  const description = body.description?.trim();
  if (!description) {
    return NextResponse.json({ error: "Description is required" }, { status: 400 });
  }

  const techStack = parseSkills(body.techStack);
  if (techStack.length < 3) {
    return NextResponse.json({ error: "At least 3 skills are required" }, { status: 400 });
  }

  if (!body.salaryRange?.trim()) {
    return NextResponse.json({ error: "Salary range is required" }, { status: 400 });
  }

  if (!isValidSalaryRange(body.salaryRange)) {
    return NextResponse.json(
      { error: 'Provide a real salary range. "Competitive" is not allowed.' },
      { status: 400 },
    );
  }

  if (!body.visaRequirements?.trim()) {
    return NextResponse.json(
      { error: "Describe who can work remotely in the US for this role." },
      { status: 400 },
    );
  }

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("owner_id", user.id)
    .maybeSingle();

  if (!company) {
    return NextResponse.json({ error: "Complete company profile first" }, { status: 400 });
  }

  const status: JobStatus = body.publish ? "active" : "draft";
  const expiresAt = body.publish ? defaultJobExpiry() : null;

  const { data: job, error } = await supabase
    .from("jobs")
    .insert({
      company_id: company.id,
      posted_by: user.id,
      title: body.title.trim(),
      description,
      role_type: body.roleType,
      experience_level: body.experienceLevel,
      tech_stack: techStack,
      salary_range: body.salaryRange.trim(),
      work_type: body.workType || "remote",
      visa_requirements: body.visaRequirements.trim(),
      status,
      expires_at: expiresAt,
      jd_quality_score: body.jdQualityScore ?? null,
      jd_quality_feedback: body.jdQualityFeedback ?? null,
    })
    .select("id")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  let matchResult = { matched: 0 };
  if (status === "active") {
    await notifyRecruitersJobPosted(job.id);
    matchResult = await runMatchingForJob(job.id);
  }

  return NextResponse.json({
    ok: true,
    jobId: job.id,
    status,
    matchesCreated: matchResult.matched,
  });
}
