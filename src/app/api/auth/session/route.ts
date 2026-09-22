import { NextRequest, NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { user, profile } = await getSessionProfile();
    if (user && profile) {
      return NextResponse.json({
        authenticated: true,
        user: {
          id: user.id,
          email: user.email,
          role: profile.role,
          full_name: profile.full_name,
        },
      });
    }
    return NextResponse.json({ authenticated: false, user: null });
  } catch {
    return NextResponse.json({ authenticated: false, user: null });
  }
}
