import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { uploadAdminCandidateResume } from "@/lib/admin-create-candidate";
import { candidatesApi } from "@/lib/api";

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

  try {
    const res = await candidatesApi.getAdminCandidateResume(id);
    if (res && res.ok && res.downloadUrl) {
      return NextResponse.redirect(res.downloadUrl);
    }
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  } catch (err: any) {
    return NextResponse.json(
      { error: err?.message || err?.error || "Resume not found" },
      { status: err?.status || 404 },
    );
  }
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
