import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { jobsApi } from "@/lib/api";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const res = await jobsApi.duplicateJob(id, { token });
    if (res && res.jobId) {
      return NextResponse.json({ ok: true, jobId: res.jobId });
    }
    return NextResponse.json({ error: "Failed to duplicate job" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to duplicate job" },
      { status: apiErr?.status || 400 },
    );
  }
}
