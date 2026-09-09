import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import type { MatchStatus } from "@/lib/types";
import { matchingApi } from "@/lib/api";

const allowedStatuses: MatchStatus[] = [
  "candidate_interested",
  "employer_shortlisted",
  "rejected",
];

export async function PATCH(request: Request) {
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

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

  try {
    const res = await matchingApi.updateMatchStatus(
      matchId,
      status as "candidate_interested" | "employer_shortlisted" | "rejected",
      { token },
    );
    if (res && res.ok) {
      return NextResponse.json({ ok: true, status: res.status });
    }
    return NextResponse.json({ error: "Failed to update match status" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to update match status" },
      { status: apiErr?.status || 400 },
    );
  }
}
