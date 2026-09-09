import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { matchingApi } from "@/lib/api";

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") return null;
  return user;
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const token = await getAccessToken();
  const { id } = await params;
  const { action } = (await request.json()) as {
    action: "approve" | "reject";
  };

  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  try {
    const res = await matchingApi.adminMatchAction(id, action, { token });
    if (res && res.ok) {
      return NextResponse.json({ ok: true });
    }
    return NextResponse.json({ error: "Action failed" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Action failed" },
      { status: apiErr?.status || 400 },
    );
  }
}
