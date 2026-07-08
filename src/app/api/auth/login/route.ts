import { NextRequest, NextResponse } from "next/server";
import { ensureProfileForUser, isAdminEmail } from "@/lib/ensure-profile";
import { createRouteHandlerClient, safeAuthNextPath } from "@/lib/supabase/auth-route";
import { getServiceClient } from "@/lib/supabase/service";
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
