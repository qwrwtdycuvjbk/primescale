import { NextResponse } from "next/server";
import { scoreJobDescription } from "@/lib/jd-quality";

export async function POST(request: Request) {
  const body = await request.json();
  const quality = await scoreJobDescription(body);
  return NextResponse.json({ quality });
}
