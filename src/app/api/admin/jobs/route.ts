import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { parseSkills } from "@/lib/matching";
import { jobsApi } from "@/lib/api";
import type { JobInput } from "@/lib/types";

export async function POST(request: Request) {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = (await request.json()) as JobInput & {
    companyId?: string;
    jdQualityScore?: number;
    jdQualityFeedback?: string;
  };
  const techStack = parseSkills(body.techStack);

  try {
    const token = await getAccessToken();
    const djangoRes = await jobsApi.createJob(
      {
        company_id: body.companyId,
        title: body.title,
        description: body.description,
        role_type: body.roleType,
        experience_level: body.experienceLevel,
        tech_stack: techStack,
        salary_range: body.salaryRange,
        work_type: body.workType,
        visa_requirements: body.visaRequirements,
        publish: body.publish,
        jd_quality_score: body.jdQualityScore,
        jd_quality_feedback: body.jdQualityFeedback,
      },
      { token },
    );

    if (djangoRes && djangoRes.ok) {
      return NextResponse.json({
        ok: true,
        jobId: djangoRes.jobId,
        status: djangoRes.status,
        matchesCreated: (djangoRes as any).matchesCreated ?? 0,
      });
    }

    return NextResponse.json({ error: "Failed to create job" }, { status: 400 });
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || err?.error || "Failed to create job" },
      { status: err?.status || 400 },
    );
  }
}
