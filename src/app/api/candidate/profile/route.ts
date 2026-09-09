import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { parseSkills } from "@/lib/matching";
import { calculateProfileCompleteness } from "@/lib/profile-completeness";
import type { CandidateProfileInput } from "@/lib/types";
import { candidatesApi } from "@/lib/api";

export async function POST(request: Request) {
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as CandidateProfileInput;
  const skills = parseSkills(body.skills);

  if (skills.length === 0) {
    return NextResponse.json({ error: "Add at least one skill" }, { status: 400 });
  }

  if (!body.resumeUrl?.trim()) {
    return NextResponse.json(
      { error: "Resume upload is required" },
      { status: 400 },
    );
  }

  const completeness = calculateProfileCompleteness(body);

  try {
    const res = await candidatesApi.saveMyProfile(
      {
        ...body,
        skills,
      },
      { token },
    );
    if (res && res.candidateProfileId) {
      return NextResponse.json({
        ok: true,
        candidateProfileId: res.candidateProfileId,
        profileCompleteness: res.profileCompleteness ?? completeness,
        matchesCreated: 0,
      });
    }
    return NextResponse.json({ error: "Failed to save profile" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to save profile" },
      { status: apiErr?.status || 400 },
    );
  }
}
