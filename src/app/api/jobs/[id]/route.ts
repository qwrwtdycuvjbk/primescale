import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import type { JobStatus } from "@/lib/types";
import { jobsApi } from "@/lib/api";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { status } = (await request.json()) as { status: JobStatus };

  try {
    const res = await jobsApi.updateJob(id, { status }, { token });
    if (res && res.ok) {
      return NextResponse.json({ ok: true });
    }
    return NextResponse.json({ error: "Failed to update job" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to update job" },
      { status: apiErr?.status || 400 },
    );
  }
}
