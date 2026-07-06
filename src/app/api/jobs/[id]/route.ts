import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { notifyRecruitersJobPosted } from "@/lib/job-notifications";
import { defaultJobExpiry } from "@/lib/employer";
import { runMatchingForJob } from "@/lib/match-runner";
import type { JobStatus } from "@/lib/types";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { status } = (await request.json()) as { status: JobStatus };

  const updates: Record<string, unknown> = {
    status,
    updated_at: new Date().toISOString(),
  };

  if (status === "active") {
    updates.expires_at = defaultJobExpiry();
  }

  const { error } = await supabase
    .from("jobs")
    .update(updates)
    .eq("id", id)
    .eq("posted_by", user.id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  if (status === "active") {
    await notifyRecruitersJobPosted(id);
    await runMatchingForJob(id);
  }

  return NextResponse.json({ ok: true });
}
