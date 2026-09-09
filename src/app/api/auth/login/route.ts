import { NextRequest, NextResponse } from "next/server";
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

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const role = parseRole(formData.get("role"));
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const nextParam = formData.get("next");
  const next = typeof nextParam === "string" && nextParam.startsWith("/") ? nextParam : "/auth/redirect";

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
    const errorMsg =
      djangoError instanceof Error
        ? djangoError.message
        : "Invalid email or password.";

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

  return NextResponse.redirect(
    new URL(
      authFormPath(role, {
        ...params,
        error: "login_failed",
        details: "Invalid email or password.",
      }),
      request.url,
    ),
  );
}
