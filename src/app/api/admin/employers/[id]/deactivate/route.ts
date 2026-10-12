import { NextRequest, NextResponse } from "next/server";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { companiesApi } from "@/lib/api/companies";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    await requireAdmin();
    const { id } = await context.params;
    const token = await getAccessToken();

    const res = await companiesApi.deactivateAdminEmployer(id, { token });
    return NextResponse.json(res);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to deactivate employer";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
