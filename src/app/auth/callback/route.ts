import { type NextRequest, NextResponse } from "next/server";
import { djangoAuth } from "@/lib/api/auth";
import { safeAuthNextPath } from "@/lib/auth-actions";
import type { UserRole } from "@/lib/types";

function parseRole(
  value: string | null | undefined,
): Extract<UserRole, "employer" | "candidate"> {
  return value === "employer" ? "employer" : "candidate";
}

function loginPathForRole(
  role: Extract<UserRole, "employer" | "candidate">,
  params?: Record<string, string>,
) {
  const base =
    role === "employer" ? "/auth/employer/login" : "/auth/candidate/login";
  if (!params || Object.keys(params).length === 0) return base;
  return `${base}?${new URLSearchParams(params).toString()}`;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const origin = request.nextUrl.origin;

  // 1. Check for OAuth error responses from Google (e.g. user cancelled prompt)
  const errorParam = searchParams.get("error");
  if (errorParam) {
    const errorDesc = searchParams.get("error_description");
    const isCancelled =
      errorParam === "access_denied" || errorParam === "user_cancelled";
    let preferredRole: string | null = searchParams.get("role");

    const stateParam = searchParams.get("state");
    if (stateParam) {
      try {
        const parsed = JSON.parse(decodeURIComponent(stateParam));
        if (parsed?.role) preferredRole = parsed.role;
      } catch {
        // ignore state parse errors
      }
    }

    return NextResponse.redirect(
      new URL(
        loginPathForRole(parseRole(preferredRole), {
          error: isCancelled ? "oauth_cancelled" : "oauth_failed",
          details: isCancelled
            ? "Sign-in with Google was cancelled."
            : errorDesc || errorParam,
        }),
        origin,
      ),
    );
  }

  // 2. Parse state parameter or search parameters
  let targetNext = searchParams.get("next");
  let preferredRole = searchParams.get("role");

  const stateParam = searchParams.get("state");
  if (stateParam) {
    try {
      const parsed = JSON.parse(decodeURIComponent(stateParam));
      if (parsed && typeof parsed === "object") {
        if (parsed.next) targetNext = parsed.next;
        if (parsed.role) preferredRole = parsed.role;
      }
    } catch {
      // ignore state parse errors and use direct params
    }
  }

  const role = parseRole(preferredRole);
  const code = searchParams.get("code");

  // 3. Verify authorization code is present
  if (!code) {
    return NextResponse.redirect(
      new URL(
        loginPathForRole(role, {
          error: "missing_code",
          details: "OAuth provider did not return an authorization code.",
        }),
        origin,
      ),
    );
  }

  // 4. Retrieve OAuth credentials
  const clientId =
    process.env.GOOGLE_CLIENT_ID ||
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    return NextResponse.redirect(
      new URL(
        loginPathForRole(role, {
          error: "oauth_misconfigured",
          details:
            "Google OAuth credentials are not fully configured on the server.",
        }),
        origin,
      ),
    );
  }

  // 5. Exchange authorization code with Google token endpoint
  const redirectUri = `${origin}/auth/callback`;
  let tokenData: { access_token?: string; id_token?: string } = {};

  try {
    const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
        grant_type: "authorization_code",
      }),
    });

    if (!tokenResponse.ok) {
      const tokenErr = await tokenResponse.json().catch(() => ({}));
      return NextResponse.redirect(
        new URL(
          loginPathForRole(role, {
            error: "oauth_failed",
            details:
              tokenErr.error_description ||
              "Failed to exchange authorization code with Google.",
          }),
          origin,
        ),
      );
    }

    tokenData = await tokenResponse.json();
  } catch (err) {
    return NextResponse.redirect(
      new URL(
        loginPathForRole(role, {
          error: "oauth_failed",
          details:
            err instanceof Error
              ? err.message
              : "Network error communicating with Google.",
        }),
        origin,
      ),
    );
  }

  // 6. Extract user identity (email and name)
  let email = "";
  let fullName = "";

  if (tokenData.access_token) {
    try {
      const userInfoRes = await fetch(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        {
          headers: { Authorization: `Bearer ${tokenData.access_token}` },
        },
      );
      if (userInfoRes.ok) {
        const userInfo = await userInfoRes.json();
        email = userInfo.email || "";
        fullName = userInfo.name || "";
      }
    } catch {
      // Fall back to id_token decoding
    }
  }

  if (!email && tokenData.id_token) {
    try {
      const parts = tokenData.id_token.split(".");
      if (parts.length >= 2) {
        const payloadJson = Buffer.from(parts[1], "base64").toString("utf-8");
        const decoded = JSON.parse(payloadJson);
        email = decoded.email || "";
        fullName = fullName || decoded.name || "";
      }
    } catch {
      // Unable to decode id_token
    }
  }

  if (!email) {
    return NextResponse.redirect(
      new URL(
        loginPathForRole(role, {
          error: "oauth_failed",
          details: "Unable to retrieve verified email from Google identity.",
        }),
        origin,
      ),
    );
  }

  // 7. Authenticate / link account in Django backend
  try {
    const authRes = await djangoAuth.googleLogin({
      email,
      full_name: fullName,
      role,
      id_token: tokenData.id_token,
    });

    if (!authRes || !authRes.access) {
      return NextResponse.redirect(
        new URL(
          loginPathForRole(role, {
            error: "oauth_failed",
            details: "Could not create or link account in People Remotely.",
          }),
          origin,
        ),
      );
    }

    // 8. Establish session via HttpOnly cookies and redirect
    const safeNext = await safeAuthNextPath(targetNext);
    const destination =
      authRes.user?.role === "admin"
        ? "/admin"
        : safeNext === "/auth/redirect"
          ? "/auth/redirect"
          : safeNext;

    const response = NextResponse.redirect(new URL(destination, origin));
    const isSecure = process.env.NODE_ENV === "production";

    response.cookies.set({
      name: "access_token",
      value: authRes.access,
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: 3600,
    });

    if (authRes.refresh) {
      response.cookies.set({
        name: "refresh_token",
        value: authRes.refresh,
        httpOnly: true,
        secure: isSecure,
        sameSite: "lax",
        path: "/api/v1/auth/",
        maxAge: 7 * 24 * 3600,
      });
    }

    return response;
  } catch (backendErr) {
    return NextResponse.redirect(
      new URL(
        loginPathForRole(role, {
          error: "oauth_failed",
          details:
            backendErr instanceof Error
              ? backendErr.message
              : "Backend authentication failed.",
        }),
        origin,
      ),
    );
  }
}
