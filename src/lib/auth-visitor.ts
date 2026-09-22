import { redirect } from "next/navigation";
import { getSessionProfile } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

type AuthRole = UserRole;

export async function handleLoggedInAuthPage(
  intendedRole: AuthRole,
  options?: { hasError?: boolean },
) {
  if (options?.hasError) return;

  const { profile } = await getSessionProfile();

  if (profile) {
    // If user's existing session role matches the page role, redirect to appropriate area
    if (profile.role === intendedRole) {
      if (profile.role === "admin") {
        redirect("/admin");
      } else if (profile.role === "employer") {
        redirect("/employer");
      } else {
        redirect("/candidate");
      }
    }
    // If the active session is for a different role, do NOT redirect to the other portal.
    // Allow the user to see the login/signup form so they can sign in to the matching portal.
  }
}