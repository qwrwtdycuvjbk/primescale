import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { defaultJobExpiry, isValidSalaryRange } from "@/lib/employer";
import { notifyRecruitersJobPosted } from "@/lib/job-notifications";
import { runMatchingForJob } from "@/lib/match-runner";
import { parseSkills } from "@/lib/matching";
import { getServiceClient } from "@/lib/supabase/service";
import type { JobInput, JobStatus } from "@/lib/types";

export async function POST(request: Request) {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const supabase = getServiceClient();
  if (!supabase) {
    return NextResponse.json(
      {
        error:
          "SUPABASE_SERVICE_ROLE_KEY is not available on the server. Add it in Vercel (Production), then redeploy.",
      },
      { status: 503 },
    );
  }

  const body = (await request.json()) as JobInput & {
    companyId?: string;
    jdQualityScore?: number;
    jdQualityFeedback?: string;
  };
  const description = body.description?.trim();
  const techStack = parseSkills(body.techStack);

  if (!body.companyId) {
    return NextResponse.json({ error: "Select a company" }, { status: 400 });
  }
  if (!body.title?.trim()) {
    return NextResponse.json({ error: "Job title is required" }, { status: 400 });
  }
  if (!description) {
    return NextResponse.json({ error: "Description is required" }, { status: 400 });
  }
  if (techStack.length < 3) {
    return NextResponse.json(
      { error: "At least 3 skills are required" },
      { status: 400 },
    );
  }
  if (!body.salaryRange?.trim() || !isValidSalaryRange(body.salaryRange)) {
    return NextResponse.json(
      { error: "Provide a real salary range" },
      { status: 400 },
    );
  }
  if (!body.visaRequirements?.trim()) {
    return NextResponse.json(
      { error: "Describe who is eligible for this role" },
      { status: 400 },
    );
  }

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("id", body.companyId)
    .maybeSingle();
  if (!company) {
    return NextResponse.json({ error: "Company not found" }, { status: 404 });
  }

  const status: JobStatus = body.publish ? "active" : "draft";
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
      expires_at: body.publish ? defaultJobExpiry() : null,
      jd_quality_score: body.jdQualityScore ?? null,
      jd_quality_feedback: body.jdQualityFeedback ?? null,
    })
    .select("id")
    .single();

  if (error || !job) {
    return NextResponse.json(
      { error: error?.message ?? "Could not add job" },
      { status: 500 },
    );
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
