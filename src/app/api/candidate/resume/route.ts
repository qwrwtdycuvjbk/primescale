import { NextResponse } from "next/server";
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

  try {
    const res = await candidatesApi.uploadResume(file, { token });
    if (res && res.downloadUrl) {
      return NextResponse.json({
        ok: true,
        url: res.downloadUrl,
        path: res.resumePath,
      });
    }
    return NextResponse.json({ error: "Failed to upload resume" }, { status: 500 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to upload resume" },
      { status: apiErr?.status || 500 },
    );
  }
}
