import type { User } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { getSessionProfile } from "@/lib/auth";
import { ensureProfileForUser } from "@/lib/ensure-profile";
import { createClient } from "@/lib/supabase/server";
import type { UserRole } from "@/lib/types";

type AuthRole = Extract<UserRole, "employer" | "candidate">;

function authPagePath(
  role: AuthRole,
  page: "login" | "signup",
  params: Record<string, string>,
) {
  const search = new URLSearchParams(params);
  const query = search.toString();
  return `/auth/${role}/${page}${query ? `?${query}` : ""}`;
}

export async function handleLoggedInAuthPage(
  user: User,
  intendedRole: AuthRole,
  options?: { hasError?: boolean; page?: "login" | "signup" },
) {
  if (options?.hasError) return;

  const page = options?.page ?? "login";
  const { profile } = await getSessionProfile();

  if (profile) {
    if (profile.role === intendedRole || profile.role === "admin") {
      redirect("/auth/redirect");
    }

    redirect(profile.role === "employer" ? "/employer" : "/candidate");
  }

  const supabase = await createClient();
  try {
    await ensureProfileForUser(supabase, user, intendedRole);
  } catch (profileError) {
    redirect(
      authPagePath(intendedRole, page, {
        error: "profile_missing",
        details:
          profileError instanceof Error
            ? profileError.message
            : "Could not load your profile.",
        ...(user.email ? { email: user.email } : {}),
      }),
    );
  }

  redirect("/auth/redirect");
}
