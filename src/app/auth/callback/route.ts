import { type NextRequest, NextResponse } from "next/server";
import { safeAuthNextPath } from "@/lib/auth-actions";
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
  const next = await safeAuthNextPath(searchParams.get("next"));
  const preferredRole = parseRole(searchParams.get("role"));

  if (!code) {
    const params = new URLSearchParams({
      error: "missing_code",
      details: "OAuth provider did not return an authorization code.",
    });
    return NextResponse.redirect(
      new URL(
        `${loginPathForRole(preferredRole)}?${params.toString()}`,
        origin,
      ),
    );
  }

  // Redirect to login or next destination with appropriate message
  return NextResponse.redirect(
    new URL(next, origin),
  );
}
