import { type NextRequest, NextResponse } from "next/server";
import { djangoAuth } from "@/lib/api/auth";

/** Email verification links — verifies Django email tokens (uid + token) */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const uid = searchParams.get("uid");
  const token = searchParams.get("token");

  // Django Email Verification Path
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

  return NextResponse.redirect(
    new URL("/auth/login?error=confirmation_failed", request.url),
  );
}
