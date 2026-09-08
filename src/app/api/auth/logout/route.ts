import { NextRequest, NextResponse } from "next/server";
import { djangoAuth } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("refresh_token")?.value;

  // 1. Invalidate Django refresh token if available
  if (refreshToken) {
    try {
      await djangoAuth.logout(refreshToken);
    } catch {
      // Best-effort
    }
  }

  // 2. Sign out of Supabase if available
  if (process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
    try {
      const supabase = await createClient();
      await supabase.auth.signOut();
    } catch {
      // Best-effort
    }
  }

  const response = NextResponse.json({ status: "ok", message: "Successfully logged out." });

  // 3. Delete cookies
  response.cookies.delete("access_token");
  response.cookies.delete("refresh_token");

  return response;
}
