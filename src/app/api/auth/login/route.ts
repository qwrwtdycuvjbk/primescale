import { NextRequest, NextResponse } from "next/server";
import { ensureProfileForUser, isAdminEmail } from "@/lib/ensure-profile";
import { createRouteHandlerClient, safeAuthNextPath } from "@/lib/supabase/auth-route";
import { getServiceClient } from "@/lib/supabase/service";
import { djangoAuth } from "@/lib/api/auth";
import type { UserRole } from "@/lib/types";

type LoginRole = Extract<UserRole, "employer" | "candidate">;

function parseRole(value: FormDataEntryValue | null): LoginRole {
  return value === "candidate" ? "candidate" : "employer";
}

function authFormPath(
  role: LoginRole,
  params: Record<string, string>,
) {
  const search = new URLSearchParams(params);
  const query = search.toString();
  return `/auth/${role}/login${query ? `?${query}` : ""}`;
}

function redirectWithCookies(
  request: NextRequest,
  sessionResponse: NextResponse,
  path: string,
) {
  const response = NextResponse.redirect(new URL(path, request.url));
  for (const cookie of sessionResponse.cookies.getAll()) {
    response.cookies.set(cookie);
  }
  return response;
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const role = parseRole(formData.get("role"));
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const next = safeAuthNextPath(formData.get("next") as string | null);

  const params: Record<string, string> = {};
  if (email) params.email = email;
  if (next !== "/auth/redirect") params.next = next;

  if (!email || !password) {
    return NextResponse.redirect(
      new URL(
        authFormPath(role, {
          ...params,
          error: "validation",
          details: "Enter your email and password.",
        }),
        request.url,
      ),
    );
  }

  const isDjangoActive = process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "supabase";

  // 1. Primary Path: Django REST Framework Authentication
  if (isDjangoActive) {
    try {
      const authRes = await djangoAuth.login({ email, password });
      if (authRes && authRes.access && authRes.user) {
        const destination =
          authRes.user.role === "admin"
            ? "/admin"
            : next === "/auth/redirect"
              ? "/auth/redirect"
              : next;

        const response = NextResponse.redirect(new URL(destination, request.url));

        // Set secure HttpOnly cookies for Next.js middleware & server components
        const isSecure = process.env.NODE_ENV === "production";
        response.cookies.set({
          name: "access_token",
          value: authRes.access,
          httpOnly: true,
          secure: isSecure,
          sameSite: "lax",
          path: "/",
          maxAge: 3600, // 60 minutes
        });

        if (authRes.refresh) {
          response.cookies.set({
            name: "refresh_token",
            value: authRes.refresh,
            httpOnly: true,
            secure: isSecure,
            sameSite: "lax",
            path: "/api/v1/auth/",
            maxAge: 7 * 24 * 3600, // 7 days
          });
        }

        return response;
      }
    } catch (djangoError: unknown) {
      // If Django returns 401 or bad credentials, return error unless Supabase fallback exists
      const errorMsg =
        djangoError instanceof Error
          ? djangoError.message
          : "Invalid email or password.";

      // If Supabase credentials exist, try fallback; otherwise redirect with error
      if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
        return NextResponse.redirect(
          new URL(
            authFormPath(role, {
              ...params,
              error: "login_failed",
              details: errorMsg,
            }),
            request.url,
          ),
        );
      }
    }
  }

  // 2. Fallback Path: Supabase Authentication (Compatibility Mode)
  const sessionResponse = NextResponse.next();
  const supabase = createRouteHandlerClient(request, sessionResponse);
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });

  if (error || !data.session || !data.user) {
    return NextResponse.redirect(
      new URL(
        authFormPath(role, {
          ...params,
          error: "login_failed",
          details:
            error?.message ??
            "Sign-in completed but no session was created. Try again.",
        }),
        request.url,
      ),
    );
  }

  if (isAdminEmail(email)) {
    const service = getServiceClient();
    const fullName =
      data.user.user_metadata?.full_name ||
      data.user.user_metadata?.name ||
      data.user.email?.split("@")[0] ||
      "Admin";

    if (service) {
      await service.from("profiles").upsert(
        {
          id: data.user.id,
          role: "admin",
          full_name: fullName,
          email: data.user.email ?? email,
        },
        { onConflict: "id" },
      );
    } else {
      await ensureProfileForUser(supabase, data.user, "admin");
    }

    return redirectWithCookies(request, sessionResponse, "/admin");
  }

  try {
    await ensureProfileForUser(supabase, data.user, role);
  } catch (profileError) {
    return NextResponse.redirect(
      new URL(
        authFormPath(role, {
          ...params,
          error: "profile_missing",
          details:
            profileError instanceof Error
              ? profileError.message
              : "Could not create profile",
        }),
        request.url,
      ),
    );
  }

  return redirectWithCookies(
    request,
    sessionResponse,
    next === "/auth/redirect" ? "/auth/redirect" : next,
  );
}
