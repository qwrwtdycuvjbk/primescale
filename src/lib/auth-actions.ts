"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { djangoAuth } from "@/lib/api/auth";
import type { UserRole } from "@/lib/types";

function parseRole(value: FormDataEntryValue | null): UserRole {
  if (value === "admin") return "admin";
  return value === "employer" ? "employer" : "candidate";
}

function authFormPath(
  role: UserRole,
  mode: "login" | "signup",
  params: Record<string, string>,
) {
  const search = new URLSearchParams(params);
  const query = search.toString();
  return `/auth/${role}/${mode}${query ? `?${query}` : ""}`;
}

export async function safeAuthNextPath(path: string | null | undefined): Promise<string> {
  if (!path || !path.startsWith("/") || path.startsWith("//")) {
    return "/auth/redirect";
  }
  return path;
}

export async function setDjangoAuthCookies(accessToken: string, refreshToken?: string) {
  const cookieStore = await cookies();
  const isSecure = process.env.NODE_ENV === "production";

  cookieStore.set({
    name: "access_token",
    value: accessToken,
    httpOnly: true,
    secure: isSecure,
    sameSite: "lax",
    path: "/",
    maxAge: 3600,
  });

  if (refreshToken) {
    cookieStore.set({
      name: "refresh_token",
      value: refreshToken,
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/api/v1/auth/",
      maxAge: 7 * 24 * 3600,
    });
  }
}

export async function clearDjangoAuthCookies() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;
  if (refreshToken) {
    try {
      await djangoAuth.logout(refreshToken);
    } catch {
      // Best-effort logout
    }
  }
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");
}

export async function signOutAuth(formData: FormData) {
  const role = formData.get("role") === "employer" ? "employer" : "candidate";
  await clearDjangoAuthCookies();
  redirect(`/auth/${role}/login`);
}

function isNextRedirect(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  if ("message" in error && (error as { message?: string }).message === "NEXT_REDIRECT") return true;
  if ("digest" in error && typeof (error as { digest?: string }).digest === "string" && (error as { digest: string }).digest.startsWith("NEXT_REDIRECT")) return true;
  return false;
}

export async function submitAuth(formData: FormData) {
  const mode = formData.get("mode") === "signup" ? "signup" : "login";
  const role = parseRole(formData.get("role"));
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const fullName = String(formData.get("fullName") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim();
  const next = await safeAuthNextPath(formData.get("next") as string | null);

  const returnParams: Record<string, string> = {};
  if (email) returnParams.email = email;
  if (next !== "/auth/redirect") returnParams.next = next;

  if (!email || !password) {
    redirect(
      authFormPath(role, mode, {
        ...returnParams,
        error: "validation",
        details: "Enter your email and password.",
      }),
    );
  }

  if (mode === "signup" && !fullName) {
    redirect(
      authFormPath(role, mode, {
        ...returnParams,
        error: "validation",
        details: "Enter your full name.",
      }),
    );
  }

  let redirectPath: string | null = null;

  if (mode === "signup") {
    if (role === "admin") {
      redirect(
        authFormPath("candidate", "signup", {
          ...returnParams,
          error: "signup_failed",
          details: "Public administrator registration is not allowed.",
        }),
      );
    }

    try {
      const regRes = await djangoAuth.register({
        email,
        password,
        full_name: fullName,
        phone: phone || null,
        role: role as "employer" | "candidate",
      });

      if (regRes && regRes.access) {
        await setDjangoAuthCookies(regRes.access, regRes.refresh);
      }

      redirectPath = authFormPath(role, mode, {
        awaiting: email,
      });
    } catch (djangoErr: unknown) {
      if (isNextRedirect(djangoErr)) {
        throw djangoErr;
      }
      const errorMsg =
        djangoErr instanceof Error
          ? djangoErr.message
          : "Registration failed. Please check your details.";
      redirectPath = authFormPath(role, mode, {
        ...returnParams,
        error: "signup_failed",
        details: errorMsg,
      });
    }
  } else {
    // Login
    try {
      const loginRes = await djangoAuth.login({ email, password });
      if (loginRes && loginRes.access && loginRes.user) {
        if (role === "admin" && loginRes.user.role !== "admin") {
          redirect(
            authFormPath("admin", "login", {
              ...returnParams,
              error: "admin_unauthorized",
              details: "This account does not have administrator access.",
            }),
          );
        }

        await setDjangoAuthCookies(loginRes.access, loginRes.refresh);
        if (loginRes.user.role === "admin") {
          redirectPath = "/admin";
        } else if (loginRes.user.role === "candidate") {
          redirectPath = "/candidate";
        } else {
          redirectPath = next === "/auth/redirect" ? "/auth/redirect" : next;
        }
      } else {
        redirectPath = "/auth/redirect";
      }
    } catch (djangoLoginErr: unknown) {
      if (isNextRedirect(djangoLoginErr)) {
        throw djangoLoginErr;
      }
      const errorMsg =
        djangoLoginErr instanceof Error
          ? djangoLoginErr.message
          : "Invalid email or password.";
      redirectPath = authFormPath(role, mode, {
        ...returnParams,
        error: "login_failed",
        details: errorMsg,
      });
    }
  }

  if (redirectPath) {
    redirect(redirectPath);
  }

  redirect("/auth/redirect");
}
