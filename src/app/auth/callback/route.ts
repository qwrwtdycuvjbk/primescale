import { type NextRequest, NextResponse } from "next/server";
import { ensureProfileForUser, preferredRoleFromUser } from "@/lib/ensure-profile";
import {
  createRouteHandlerClient,
  safeAuthNextPath,
} from "@/lib/supabase/auth-route";
import { djangoAuth } from "@/lib/api/auth";
import type { UserRole } from "@/lib/types";

function parseRole(
  value: string | null,
): Extract<UserRole, "employer" | "candidate"> | null {
  if (value === "employer" || value === "candidate") return value;
  return null;
}

function loginPathForRole(
  role: Extract<UserRole, "employer" | "candidate"> | null,
) {
  return role === "employer" ? "/auth/employer/login" : "/auth/candidate/login";
}

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeAuthNextPath(searchParams.get("next"));
  const preferredRole = parseRole(searchParams.get("role"));

  if (!code) {
    const params = new URLSearchParams({
      error: "missing_code",
      details: "Google did not return a sign-in code. Check Supabase redirect URLs.",
    });
    return NextResponse.redirect(
      new URL(
        `${loginPathForRole(preferredRole)}?${params.toString()}`,
        origin,
      ),
    );
  }

  const response = NextResponse.redirect(new URL(next, origin));
  const supabase = createRouteHandlerClient(request, response);
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    const params = new URLSearchParams({
      error: "confirmation_failed",
      details: error.message,
    });
    return NextResponse.redirect(
      new URL(
        `${loginPathForRole(preferredRole)}?${params.toString()}`,
        origin,
      ),
    );
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    // 1. Sync / Link with Django backend
    if (user.email) {
      try {
        const role =
          preferredRole ??
          (preferredRoleFromUser(user) === "employer" ? "employer" : "candidate");
        const djangoRes = await djangoAuth.googleLogin({
          email: user.email,
          full_name:
            user.user_metadata?.full_name ||
            user.user_metadata?.name ||
            user.email.split("@")[0],
          role,
        });

        if (djangoRes && djangoRes.access) {
          const isSecure = process.env.NODE_ENV === "production";
          response.cookies.set({
            name: "access_token",
            value: djangoRes.access,
            httpOnly: true,
            secure: isSecure,
            sameSite: "lax",
            path: "/",
            maxAge: 3600,
          });

          if (djangoRes.refresh) {
            response.cookies.set({
              name: "refresh_token",
              value: djangoRes.refresh,
              httpOnly: true,
              secure: isSecure,
              sameSite: "lax",
              path: "/api/v1/auth/",
              maxAge: 7 * 24 * 3600,
            });
          }
        }
      } catch {
        // Fallback continues with Supabase session
      }
    }

    // 2. Ensure profile for Supabase compatibility
    try {
      await ensureProfileForUser(supabase, user, preferredRole);
    } catch (profileError) {
      const role =
        preferredRole ??
        (preferredRoleFromUser(user) === "employer" ? "employer" : "candidate");
      const params = new URLSearchParams({
        error: "profile_missing",
        details:
          profileError instanceof Error
            ? profileError.message
            : "Could not create profile",
      });
      if (user.email) params.set("email", user.email);
      return NextResponse.redirect(
        new URL(`${loginPathForRole(role)}?${params.toString()}`, origin),
      );
    }
  }

  return response;
}
