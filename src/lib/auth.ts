import { createClient } from "@/lib/supabase/server";
import { getServiceClient } from "@/lib/supabase/service";
import { ensureProfileForUser, isAdminEmail, preferredRoleFromUser } from "@/lib/ensure-profile";
import { redirect } from "next/navigation";
import type { Profile, UserRole } from "@/lib/types";
import type { User } from "@supabase/supabase-js";

async function loadAdminProfile(user: User): Promise<Profile | null> {
  const service = getServiceClient();
  if (!service || !isAdminEmail(user.email)) return null;

  const { data: existing } = await service
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (existing?.role === "admin") {
    return existing;
  }

  const fullName =
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    user.email?.split("@")[0] ||
    "Admin";

  const { data: profile } = await service
    .from("profiles")
    .upsert(
      {
        id: user.id,
        role: "admin",
        full_name: fullName,
        email: user.email ?? "",
      },
      { onConflict: "id" },
    )
    .select("*")
    .single();

  return profile;
}

export async function getSessionProfile() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { user: null, profile: null };

  const { data: profile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (profile) {
    if (isAdminEmail(user.email) && profile.role !== "admin") {
      const adminProfile = await loadAdminProfile(user);
      if (adminProfile) return { user, profile: adminProfile };
    }

    return { user, profile };
  }

  if (isAdminEmail(user.email)) {
    const adminProfile = await loadAdminProfile(user);
    if (adminProfile) return { user, profile: adminProfile };
  }

  const preferredRole = preferredRoleFromUser(user);

  try {
    await ensureProfileForUser(supabase, user, preferredRole);
  } catch {
    const service = getServiceClient();
    if (service) {
      const role =
        preferredRole ??
        preferredRoleFromUser(user) ??
        (isAdminEmail(user.email) ? "admin" : "candidate");
      await service.from("profiles").upsert(
        {
          id: user.id,
          role,
          full_name:
            user.user_metadata?.full_name ||
            user.user_metadata?.name ||
            user.email?.split("@")[0] ||
            "User",
          email: user.email ?? "",
        },
        { onConflict: "id" },
      );
    }
  }

  const { data: ensuredProfile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (ensuredProfile) return { user, profile: ensuredProfile };

  const service = getServiceClient();
  if (service) {
    const { data: serviceProfile } = await service
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .maybeSingle();
    if (serviceProfile) return { user, profile: serviceProfile };
  }

  if (isAdminEmail(user.email)) {
    const adminProfile = await loadAdminProfile(user);
    return { user, profile: adminProfile };
  }

  return { user, profile: null };
}

export async function requireRole(role: UserRole) {
  const { user, profile } = await getSessionProfile();

  if (!user) {
    redirect(`/auth/${role}/login?next=/${role}`);
  }

  if (!profile) {
    redirect("/auth/redirect");
  }

  if (profile.role !== role && profile.role !== "admin") {
    redirect(profile.role === "employer" ? "/employer" : "/candidate");
  }

  return { user, profile };
}

export async function requireAdmin() {
  const { user, profile } = await getSessionProfile();

  if (!user || !profile || profile.role !== "admin") {
    redirect("/auth/employer/login?next=/admin/handoffs");
  }

  return { user, profile };
}

export function redirectIfLoggedIn() {
  redirect("/auth/redirect");
}
