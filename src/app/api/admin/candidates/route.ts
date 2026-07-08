import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import {
  createAdminCandidate,
  type AdminCreateCandidateInput,
} from "@/lib/admin-create-candidate";

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") return null;
  return user;
}

export async function POST(request: Request) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = (await request.json()) as AdminCreateCandidateInput;
  const result = await createAdminCandidate(body);

  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }

  return NextResponse.json({
    ok: true,
    candidateProfileId: result.candidateProfileId,
    userId: result.userId,
    matchesCreated: result.matchesCreated,
  });
}
