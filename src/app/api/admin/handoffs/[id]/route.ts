import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import type { HandoffStatus } from "@/lib/types";
import { handoffsApi } from "@/lib/api";

const allowedStatuses: HandoffStatus[] = [
  "pending",
  "contacted",
  "intro_made",
  "closed",
];

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") {
    return null;
  }
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
  const { status, notes } = (await request.json()) as {
    status?: HandoffStatus;
    notes?: string;
  };

  if (status && !allowedStatuses.includes(status)) {
    return NextResponse.json({ error: "Invalid status" }, { status: 400 });
  }

  try {
    const res = await handoffsApi.updateHandoff(
      id,
      {
        status,
        notes,
      },
      { token },
    );
    if (res && res.ok) {
      return NextResponse.json({ ok: true });
    }
    return NextResponse.json({ error: "Failed to update handoff" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to update handoff" },
      { status: apiErr?.status || 400 },
    );
  }
}
