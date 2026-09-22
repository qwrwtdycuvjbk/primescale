import { NextRequest, NextResponse } from "next/server";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { candidatesApi } from "@/lib/api";

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    await requireAdmin();
    const { id } = await context.params;
    const token = await getAccessToken();

    const res = await candidatesApi.deleteAdminCandidate(id, { token });
    return NextResponse.json(res);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to delete candidate account";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
