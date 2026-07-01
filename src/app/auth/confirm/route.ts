import { type EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";
import {
  createRouteHandlerClient,
  safeAuthNextPath,
} from "@/lib/supabase/auth-route";

/** Email verification links only — Google OAuth uses /auth/callback (client). */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const code = searchParams.get("code");
  const next = safeAuthNextPath(searchParams.get("next"));

  if (token_hash && type) {
    const response = NextResponse.redirect(new URL(next, request.url));
    const supabase = createRouteHandlerClient(request, response);
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) return response;
  }

  if (code) {
    const response = NextResponse.redirect(new URL(next, request.url));
    const supabase = createRouteHandlerClient(request, response);
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return response;
  }

  return NextResponse.redirect(
    new URL("/auth/login?error=confirmation_failed", request.url),
  );
}
