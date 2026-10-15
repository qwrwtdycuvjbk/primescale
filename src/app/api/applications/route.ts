import { NextRequest, NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { applicationsApi } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { user } = await getSessionProfile();
    const token = await getAccessToken();

    if (!user || !token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const jobId = searchParams.get("job_id") || undefined;

    const apps = await applicationsApi.listApplications(
      jobId ? { job_id: jobId } : undefined,
      { token },
    );
    return NextResponse.json({ ok: true, applications: apps });
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || "Failed to fetch applications" },
      { status: err?.status || 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const { user, profile } = await getSessionProfile();
    const token = await getAccessToken();

    if (!user || !token) {
      return NextResponse.json({ error: "Authentication required" }, { status: 401 });
    }

    if (profile?.role !== "candidate") {
      const msg =
        profile?.role === "employer"
          ? "You are currently logged in as an employer. To apply for jobs, please go back, create a separate candidate profile, and log in using your candidate account."
          : "Only candidates can apply to jobs.";
      return NextResponse.json({ error: msg }, { status: 403 });
    }

    const body = await request.json();
    const jobId = body.job_id || body.jobId;
    const coverNote = body.cover_note || body.coverNote;

    if (!jobId) {
      return NextResponse.json({ error: "Job ID is required" }, { status: 400 });
    }

    const res = await applicationsApi.apply(jobId, coverNote, { token });
    return NextResponse.json({ ok: true, application: res.application }, { status: 201 });
  } catch (apiErr: any) {
    const status = apiErr?.status || 400;
    const errorMsg =
      apiErr?.data?.error ||
      (typeof apiErr?.data === "object" && apiErr?.data?.job_id
        ? Array.isArray(apiErr.data.job_id)
          ? apiErr.data.job_id.join(" ")
          : String(apiErr.data.job_id)
        : null) ||
      apiErr?.message ||
      "Failed to submit application";

    return NextResponse.json({ error: errorMsg }, { status });
  }
}
