import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

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

  const ext = file.name.split(".").pop() ?? "png";
  const path = `${user.id}/logo-${Date.now()}.${ext}`;

  const { error } = await supabase.storage
    .from("company-logos")
    .upload(path, file, { upsert: true });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const { data } = supabase.storage.from("company-logos").getPublicUrl(path);
  return NextResponse.json({ ok: true, url: data.publicUrl });
}
