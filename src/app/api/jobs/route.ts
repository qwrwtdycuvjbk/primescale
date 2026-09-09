import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { isValidSalaryRange } from "@/lib/employer";
import { parseSkills } from "@/lib/matching";
import type { JobInput, JobStatus } from "@/lib/types";
import { jobsApi, companiesApi } from "@/lib/api";

export async function POST(request: Request) {
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

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

  let companyId: string | null = null;
  try {
    const comp = await companiesApi.getMyCompany({ token });
    if (comp && comp.id) {
      companyId = comp.id;
    }
  } catch (err) {
    console.error("Failed to fetch employer company:", err);
  }

  if (!companyId) {
    return NextResponse.json({ error: "Complete company profile first" }, { status: 400 });
  }

  const status: JobStatus = body.publish ? "active" : "draft";

  try {
    const djangoRes = await jobsApi.createJob(
      {
        company_id: companyId,
        title: body.title.trim(),
        description,
        role_type: body.roleType,
        experience_level: body.experienceLevel,
        tech_stack: techStack,
        salary_range: body.salaryRange.trim(),
        work_type: body.workType || "remote",
        visa_requirements: body.visaRequirements.trim(),
        publish: body.publish,
        status,
        jd_quality_score: body.jdQualityScore ?? null,
        jd_quality_feedback: body.jdQualityFeedback ?? null,
      },
      { token },
    );

    if (djangoRes && djangoRes.jobId) {
      return NextResponse.json({
        ok: true,
        jobId: djangoRes.jobId,
        status: djangoRes.status,
        matchesCreated: (djangoRes as any).matchesCreated ?? 0,
      });
    }

    return NextResponse.json({ error: "Failed to create job" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to create job" },
      { status: apiErr?.status || 400 },
    );
  }
}
