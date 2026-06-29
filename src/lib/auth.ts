import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import type { UserRole } from "@/lib/types";

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
    .single();

  return { user, profile };
}

export async function requireRole(role: UserRole) {
  const { user, profile } = await getSessionProfile();

  if (!user || !profile) {
    redirect(`/auth/login?next=/${role}`);
  }

  if (profile.role !== role && profile.role !== "admin") {
    const other = profile.role === "employer" ? "/employer" : "/candidate";
    redirect(other);
  }

  return { user, profile };
}
