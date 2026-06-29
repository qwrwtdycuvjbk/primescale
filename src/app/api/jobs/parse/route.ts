import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { parseJobDescriptionWithLlm } from "@/lib/matching";

export async function POST(request: Request) {
  const { pastedJd } = await request.json();

  if (!pastedJd?.trim()) {
    return NextResponse.json({ error: "Job description required" }, { status: 400 });
  }

  const parsed = await parseJobDescriptionWithLlm(pastedJd);

  return NextResponse.json({ parsed });
}
