import { NextRequest, NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import { candidatesApi } from "@/lib/api";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { user, profile } = await getSessionProfile();
    if (user && profile) {
      let candidateProfile = null;
      let isProfileComplete = false;

      if (profile.role === "candidate") {
        try {
          const token = await getAccessToken();
          candidateProfile = await candidatesApi.getMyProfile({ token });
          isProfileComplete = isCandidateProfileComplete(candidateProfile);
        } catch {
          isProfileComplete = false;
        }
      }

      return NextResponse.json({
        authenticated: true,
        user: {
          id: user.id,
          email: user.email,
          role: profile.role,
          full_name: profile.full_name,
        },
        candidateProfile,
        isProfileComplete,
      });
    }
    return NextResponse.json({ authenticated: false, user: null, candidateProfile: null, isProfileComplete: false });
  } catch {
    return NextResponse.json({ authenticated: false, user: null, candidateProfile: null, isProfileComplete: false });
  }
}
