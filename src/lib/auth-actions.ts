"use server";

import type { User } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { ensureProfileForUser, isAdminEmail } from "@/lib/ensure-profile";
import { getServiceClient } from "@/lib/supabase/service";
import { safeAuthNextPath } from "@/lib/supabase/auth-route";
import type { UserRole } from "@/lib/types";

function parseRole(value: FormDataEntryValue | null): Extract<
  UserRole,
  "employer" | "candidate"
> {
  return value === "employer" ? "employer" : "candidate";
}

function authFormPath(
  role: Extract<UserRole, "employer" | "candidate">,
  mode: "login" | "signup",
  params: Record<string, string>,
) {
  const search = new URLSearchParams(params);
  const query = search.toString();
  return `/auth/${role}/${mode}${query ? `?${query}` : ""}`;
}

async function savePhone(userId: string, phone: string) {
  if (!phone.trim()) return;
  const supabase = await createClient();
  await supabase.from("profiles").update({ phone: phone.trim() }).eq("id", userId);
}

async function ensureAdminProfile(
  supabase: Awaited<ReturnType<typeof createClient>>,
  user: User,
  email: string,
) {
  await ensureProfileForUser(supabase, user, "admin");

  const service = getServiceClient();
  if (!service) return;

  await service.from("profiles").upsert(
    {
      id: user.id,
      role: "admin",
      full_name:
        user.user_metadata?.full_name ||
        user.user_metadata?.name ||
        email.split("@")[0] ||
        "Admin",
      email: user.email ?? email,
    },
    { onConflict: "id" },
  );
}

export async function signOutAuth(formData: FormData) {
  const role = formData.get("role") === "employer" ? "employer" : "candidate";
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect(`/auth/${role}/login`);
}

export async function submitAuth(formData: FormData) {
  const mode = formData.get("mode") === "signup" ? "signup" : "login";
  const role = parseRole(formData.get("role"));
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const fullName = String(formData.get("fullName") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim();
  const next = safeAuthNextPath(formData.get("next") as string | null);
  const adminLogin = isAdminEmail(email);

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

  const supabase = await createClient();

  if (mode === "signup") {
    const origin = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
    const destination = encodeURIComponent("/auth/redirect");
    const signupRole = adminLogin ? "admin" : role;
    const emailRedirectTo = `${origin}/auth/confirm?next=${destination}&role=${signupRole}`;

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          role: signupRole,
          full_name: fullName,
          phone: phone || undefined,
        },
        emailRedirectTo,
      },
    });

    if (error) {
      redirect(
        authFormPath(role, mode, {
          ...returnParams,
          error: "signup_failed",
          details: error.message,
        }),
      );
    }

    if (data.session && data.user) {
      await savePhone(data.user.id, phone);
      if (adminLogin) {
        await ensureAdminProfile(supabase, data.user, email);
        redirect("/admin/handoffs");
      }
      try {
        await ensureProfileForUser(supabase, data.user, role);
      } catch (profileError) {
        redirect(
          authFormPath(role, mode, {
            ...returnParams,
            error: "profile_missing",
            details:
              profileError instanceof Error
                ? profileError.message
                : "Could not create profile",
          }),
        );
      }
      redirect("/auth/redirect");
    }

    redirect(
      authFormPath(role, mode, {
        awaiting: email,
      }),
    );
  }

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    redirect(
      authFormPath(role, mode, {
        ...returnParams,
        error: "login_failed",
        details: error.message,
      }),
    );
  }

  if (!data.session) {
    redirect(
      authFormPath(role, mode, {
        ...returnParams,
        error: "login_failed",
        details: "Sign-in completed but no session was created. Try again.",
      }),
    );
  }

  if (data.user) {
    await savePhone(data.user.id, phone);
    if (adminLogin) {
      await ensureAdminProfile(supabase, data.user, email);
      redirect("/admin/handoffs");
    }
    try {
      await ensureProfileForUser(supabase, data.user, role);
    } catch (profileError) {
      redirect(
        authFormPath(role, mode, {
          ...returnParams,
          error: "profile_missing",
          details:
            profileError instanceof Error
              ? profileError.message
              : "Could not create profile",
        }),
      );
    }
  }

  redirect("/auth/redirect");
}
