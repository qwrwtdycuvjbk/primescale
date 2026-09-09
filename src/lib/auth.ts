import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { djangoAuth } from "@/lib/api/auth";
import type { Profile, UserRole } from "@/lib/types";

interface SessionUser {
  id: string;
  email?: string;
  user_metadata?: Record<string, unknown>;
}

/**
 * Retrieves authenticated user from Django backend via HttpOnly cookies (access_token / refresh_token).
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
 * Authoritative Django session resolution.
 */
export const getSessionProfile = cache(async () => {
  const djangoSession = await getDjangoSessionProfile();
  if (djangoSession && djangoSession.user) {
    return djangoSession;
  }
  return { user: null, profile: null };
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
