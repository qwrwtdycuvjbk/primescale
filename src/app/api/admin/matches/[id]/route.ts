import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { getServiceClient } from "@/lib/supabase/service";
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

  const { id } = await params;
  const { action } = (await request.json()) as {
    action: "approve" | "reject";
  };

  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  }

  // Attempt Django REST API admin match action
  try {
    const res = await matchingApi.adminMatchAction(id, action);
    if (res && res.ok) {
      return NextResponse.json({ ok: true });
    }
  } catch (apiErr) {
    // Fall back to Supabase database during progressive migration phase
  }

  const supabase = getServiceClient();
  if (!supabase) {
    return NextResponse.json({ error: "Service unavailable" }, { status: 503 });
  }

  const updates =
    action === "approve"
      ? {
          visible_to_employer: true,
          updated_at: new Date().toISOString(),
        }
      : {
          visible_to_employer: false,
          status: "rejected",
          updated_at: new Date().toISOString(),
        };

  const { error } = await supabase.from("matches").update(updates).eq("id", id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}

