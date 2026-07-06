import { NextResponse } from "next/server";
import { createMutualFitHandoff, resolveMatchStatus } from "@/lib/handoff";
import { createClient } from "@/lib/supabase/server";
import type { MatchStatus } from "@/lib/types";

const allowedStatuses: MatchStatus[] = [
  "candidate_interested",
  "employer_shortlisted",
  "rejected",
];

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

  if (!allowedStatuses.includes(status)) {
    return NextResponse.json({ error: "Invalid status" }, { status: 400 });
  }

  const { data: current, error: readError } = await supabase
    .from("matches")
    .select("id, status")
    .eq("id", matchId)
    .single();

  if (readError || !current) {
    return NextResponse.json({ error: "Match not found" }, { status: 404 });
  }

  if (current.status === "mutual_fit" || current.status === "rejected") {
    return NextResponse.json({ error: "Match is already closed" }, { status: 400 });
  }

  const finalStatus = resolveMatchStatus(current.status, status);

  const { error } = await supabase
    .from("matches")
    .update({ status: finalStatus, updated_at: new Date().toISOString() })
    .eq("id", matchId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  if (finalStatus === "mutual_fit") {
    await createMutualFitHandoff(matchId);
  }

  return NextResponse.json({ ok: true, status: finalStatus });
}
