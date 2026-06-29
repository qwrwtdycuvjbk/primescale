import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import type { MatchStatus } from "@/lib/types";

export async function PATCH(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { matchId, status } = (await request.json()) as {
    matchId: string;
    status: MatchStatus;
  };

  const { error } = await supabase
    .from("matches")
    .update({ status, updated_at: new Date().toISOString() })
    .eq("id", matchId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
