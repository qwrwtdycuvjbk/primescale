import { redirect } from "next/navigation";
import { getSessionProfile } from "@/lib/auth";
import type { UserRole } from "@/lib/types";

type AuthRole = Extract<UserRole, "employer" | "candidate">;

export async function handleLoggedInAuthPage(
  intendedRole: AuthRole,
  options?: { hasError?: boolean },
) {
  if (options?.hasError) return;

  const { profile } = await getSessionProfile();

  if (profile) {
    if (profile.role === intendedRole || profile.role === "admin") {
      redirect("/auth/redirect");
    }

    redirect(profile.role === "employer" ? "/employer" : "/candidate");
  }
}
