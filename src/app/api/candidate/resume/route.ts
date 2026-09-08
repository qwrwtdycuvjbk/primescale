import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { candidatesApi } from "@/lib/api";

export async function POST(request: Request) {
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const formData = await request.formData();
  const file = formData.get("file");

  if (!file || !(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  const allowed = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  if (!allowed.includes(file.type)) {
    return NextResponse.json(
      { error: "Only PDF or DOCX files are allowed" },
      { status: 400 },
    );
  }

  // Attempt Django REST API upload
  try {
    const res = await candidatesApi.uploadResume(file, { token });
    if (res && res.downloadUrl) {
      return NextResponse.json({
        ok: true,
        url: res.downloadUrl,
        path: res.resumePath,
      });
    }
  } catch (apiErr) {
    // Fall back to Supabase Storage during progressive migration phase
  }

  const supabase = await createClient();

  const ext = file.name.split(".").pop() ?? "pdf";
  const path = `${user.id}/resume-${Date.now()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from("resumes")
    .upload(path, file, { upsert: true });

  if (uploadError) {
    return NextResponse.json({ error: uploadError.message }, { status: 500 });
  }

  const {
    data: { publicUrl },
  } = supabase.storage.from("resumes").getPublicUrl(path);

  return NextResponse.json({
    ok: true,
    url: publicUrl,
    path,
  });
}

