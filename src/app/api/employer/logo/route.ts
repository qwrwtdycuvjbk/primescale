import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { companiesApi } from "@/lib/api";

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

  if (!file.type.startsWith("image/")) {
    return NextResponse.json({ error: "Image files only" }, { status: 400 });
  }

  try {
    const res = await companiesApi.uploadLogo(file, { token });
    if (res && res.url) {
      return NextResponse.json({ ok: true, url: res.url });
    }
    return NextResponse.json({ error: "Failed to upload logo" }, { status: 500 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to upload logo" },
      { status: apiErr?.status || 500 },
    );
  }
}
