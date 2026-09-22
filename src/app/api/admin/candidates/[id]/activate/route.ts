import { NextRequest, NextResponse } from "next/server";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { candidatesApi } from "@/lib/api";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    await requireAdmin();
    const { id } = await context.params;
    const token = await getAccessToken();

    const res = await candidatesApi.activateAdminCandidate(id, { token });
    return NextResponse.json(res);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to activate candidate";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
