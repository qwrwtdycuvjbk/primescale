import { type NextRequest, NextResponse } from "next/server";
import { ensureProfileForUser, preferredRoleFromUser } from "@/lib/ensure-profile";
import {
  createRouteHandlerClient,
  safeAuthNextPath,
} from "@/lib/supabase/auth-route";
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
