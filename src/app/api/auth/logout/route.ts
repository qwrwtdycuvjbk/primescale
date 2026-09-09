import { NextRequest, NextResponse } from "next/server";
import { djangoAuth } from "@/lib/api/auth";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("refresh_token")?.value;

  // 1. Invalidate Django refresh token
  if (refreshToken) {
    try {
      await djangoAuth.logout(refreshToken);
    } catch {
      // Best-effort
    }
  }

  const response = NextResponse.json({ status: "ok", message: "Successfully logged out." });

  // 2. Delete cookies
  response.cookies.delete("access_token");
  response.cookies.delete("refresh_token");

  return response;
}
