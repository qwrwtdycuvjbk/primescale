import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import type { HandoffStatus } from "@/lib/types";

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

  const { id } = await params;
  const { status, notes } = (await request.json()) as {
    status?: HandoffStatus;
    notes?: string;
  };

  if (status && !allowedStatuses.includes(status)) {
    return NextResponse.json({ error: "Invalid status" }, { status: 400 });
  }

  const supabase = await createClient();
  const updates: { status?: HandoffStatus; notes?: string; updated_at: string } =
    {
      updated_at: new Date().toISOString(),
    };

  if (status) updates.status = status;
  if (notes !== undefined) updates.notes = notes;

  const { error } = await supabase
    .from("handoff_requests")
    .update(updates)
    .eq("id", id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
