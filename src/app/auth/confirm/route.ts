import { type EmailOtpType } from "@supabase/supabase-js";
import { type NextRequest, NextResponse } from "next/server";
import { ensureProfileForUser } from "@/lib/ensure-profile";
import {
  createRouteHandlerClient,
  safeAuthNextPath,
} from "@/lib/supabase/auth-route";
import { djangoAuth } from "@/lib/api/auth";
import type { UserRole } from "@/lib/types";

function parseConfirmedRole(
  value: string | null,
): Extract<UserRole, "employer" | "candidate" | "admin"> | null {
  if (value === "employer" || value === "candidate" || value === "admin") {
    return value;
  }
  return null;
}

/** Email verification links — supports both Django tokens (uid + token) and Supabase (token_hash). */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;
  const code = searchParams.get("code");
  const next = safeAuthNextPath(searchParams.get("next"));
  const confirmedRole = parseConfirmedRole(searchParams.get("role"));

  // 1. Django Email Verification Path
  if (uid && token) {
    try {
      const verifyRes = await djangoAuth.verifyEmail({ uid, token });
      if (verifyRes && verifyRes.user) {
        const loginPath =
          verifyRes.user.role === "employer"
            ? "/auth/employer/login"
            : "/auth/candidate/login";
        return NextResponse.redirect(
          new URL(`${loginPath}?verified=true`, request.url),
        );
      }
    } catch {
      return NextResponse.redirect(
        new URL("/auth/login?error=confirmation_failed&details=Verification+link+is+invalid+or+has+expired.", request.url),
      );
    }
  }

  // 2. Supabase Email Verification Path (Compatibility Mode)
  if (token_hash && type) {
    const response = NextResponse.redirect(new URL(next, request.url));
    const supabase = createRouteHandlerClient(request, response);
    const { error } = await supabase.auth.verifyOtp({ type, token_hash });
    if (!error) {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user) {
        await ensureProfileForUser(supabase, user, confirmedRole);
      }
      return response;
    }
  }

  if (code) {
    const response = NextResponse.redirect(new URL(next, request.url));
    const supabase = createRouteHandlerClient(request, response);
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user) {
        await ensureProfileForUser(supabase, user, confirmedRole);
      }
      return response;
    }
  }

  return NextResponse.redirect(
    new URL("/auth/login?error=confirmation_failed", request.url),
  );
}
