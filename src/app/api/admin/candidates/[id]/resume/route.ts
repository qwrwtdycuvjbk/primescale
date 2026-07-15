import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { uploadAdminCandidateResume } from "@/lib/admin-create-candidate";
import { resumeStoragePath } from "@/lib/resume-storage";
import { getServiceClient } from "@/lib/supabase/service";

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") return null;
  return user;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { id } = await params;
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

  const { data: candidate, error } = await supabase
    .from("candidate_profiles")
    .select("resume_url")
    .eq("id", id)
    .maybeSingle();

  if (error || !candidate?.resume_url) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  const path = resumeStoragePath(candidate.resume_url);
  if (!path) {
    return NextResponse.json({ error: "Invalid resume path" }, { status: 400 });
  }

  const { data, error: signedError } = await supabase.storage
    .from("resumes")
    .createSignedUrl(path, 60 * 60);

  if (signedError || !data?.signedUrl) {
    return NextResponse.json(
      { error: signedError?.message ?? "Could not open resume" },
      { status: 500 },
    );
  }

  return NextResponse.redirect(data.signedUrl);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { id } = await params;
  const formData = await request.formData();
  const file = formData.get("file");

  if (!file || !(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  const result = await uploadAdminCandidateResume(id, file);

  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }

  return NextResponse.json({ ok: true, resumeUrl: result.resumeUrl });
}
