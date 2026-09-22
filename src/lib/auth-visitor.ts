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
    if (profile.role === "admin") {
      redirect("/admin");
    }

    if (intendedRole === "admin") {
      // Allow non-admin user to access admin login page to sign in with admin credentials
      return;
    }

    if (profile.role === intendedRole) {
      redirect("/auth/redirect");
    }

    redirect(profile.role === "employer" ? "/employer" : "/candidate");
  }
}
