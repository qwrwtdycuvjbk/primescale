import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getServiceClient } from "@/lib/supabase/service";
import { ensureProfileForUser, isAdminEmail, preferredRoleFromUser } from "@/lib/ensure-profile";
import { djangoAuth } from "@/lib/api/auth";
import type { Profile, UserRole } from "@/lib/types";
import type { User } from "@supabase/supabase-js";

interface SessionUser {
  id: string;
  email?: string;
  user_metadata?: Record<string, unknown>;
}

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

/**
 * Attempts to retrieve authenticated user from Django backend via HttpOnly cookies.
 */
async function getDjangoSessionProfile(): Promise<{
  user: SessionUser | null;
  profile: Profile | null;
} | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value;
  const refreshToken = cookieStore.get("refresh_token")?.value;

  if (!accessToken && !refreshToken) {
    return null;
  }

  // 1. Try with existing access token
  if (accessToken) {
    try {
      const djangoUser = await djangoAuth.getCurrentUser(accessToken);
      if (djangoUser && djangoUser.id) {
        return {
          user: {
            id: djangoUser.id,
            email: djangoUser.email,
            user_metadata: {
              full_name: djangoUser.full_name,
              role: djangoUser.role,
              phone: djangoUser.phone,
            },
          },
          profile: djangoUser,
        };
      }
    } catch {
      // Access token expired or invalid; proceed to refresh below
    }
  }

  // 2. Try refreshing token if refresh_token cookie exists
  if (refreshToken) {
    try {
      const tokens = await djangoAuth.refreshToken(refreshToken);
      if (tokens.access) {
        const djangoUser = await djangoAuth.getCurrentUser(tokens.access);
        if (djangoUser && djangoUser.id) {
          return {
            user: {
              id: djangoUser.id,
              email: djangoUser.email,
              user_metadata: {
                full_name: djangoUser.full_name,
                role: djangoUser.role,
                phone: djangoUser.phone,
              },
            },
            profile: djangoUser,
          };
        }
      }
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Deduped per request so layout + page don't re-run auth/profile lookups.
 * Priority:
 * 1. If Django session is active, returns Django authenticated user & profile.
 * 2. If no Django session, falls back to Supabase session (compatibility mode).
 */
export const getSessionProfile = cache(async () => {
  const isDjangoActive = process.env.NEXT_PUBLIC_AUTH_PROVIDER !== "supabase";

  if (isDjangoActive) {
    const djangoSession = await getDjangoSessionProfile();
    if (djangoSession && djangoSession.user) {
      return djangoSession;
    }
  }

  // Supabase Fallback / Compatibility Mode
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
});

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
    redirect("/auth/employer/login?next=/admin");
  }

  return { user, profile };
}

export function redirectIfLoggedIn() {
  redirect("/auth/redirect");
}

/**
 * Returns access token from cookies if present for server component API requests.
 */
export async function getAccessToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value;
}
