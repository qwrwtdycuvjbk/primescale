import type { SupabaseClient, User } from "@supabase/supabase-js";
import type { UserRole } from "@/lib/types";

function profileNameFromUser(user: User) {
  return (
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    user.email?.split("@")[0] ||
    "User"
  );
}

function normalizeRole(role: string | null | undefined): UserRole {
  if (role === "employer" || role === "candidate") return role;
  return "candidate";
}

export async function ensureProfileForUser(
  supabase: SupabaseClient,
  user: User,
  preferredRole?: UserRole | null,
) {
  const { error: rpcError } = await supabase.rpc("ensure_user_profile", {
    p_role: preferredRole ?? null,
  });

  if (!rpcError) {
    const { data: profile } = await supabase
      .from("profiles")
      .select("role, full_name")
      .eq("id", user.id)
      .maybeSingle();

    if (profile) return profile;
  }

  const fullName = profileNameFromUser(user);
  const { data: existing } = await supabase
    .from("profiles")
    .select("id, role, full_name")
    .eq("id", user.id)
    .maybeSingle();

  if (!existing) {
    const role = normalizeRole(preferredRole ?? user.user_metadata?.role);
    const phone =
      typeof user.user_metadata?.phone === "string"
        ? user.user_metadata.phone
        : null;

    const { error: insertError } = await supabase.from("profiles").insert({
      id: user.id,
      role,
      full_name: fullName,
      email: user.email ?? "",
      ...(phone ? { phone } : {}),
    });

    if (insertError) {
      throw new Error(insertError.message);
    }

    return { role, full_name: fullName };
  }

  const phone =
    typeof user.user_metadata?.phone === "string"
      ? user.user_metadata.phone
      : null;

  const updates: { role?: UserRole; full_name?: string; phone?: string } = {};
  if (preferredRole === "employer" || preferredRole === "candidate") {
    updates.role = preferredRole;
  }
  if (!existing.full_name && fullName) {
    updates.full_name = fullName;
  }
  if (phone) {
    updates.phone = phone;
  }

  if (Object.keys(updates).length > 0) {
    const { error: updateError } = await supabase
      .from("profiles")
      .update(updates)
      .eq("id", user.id);

    if (updateError) {
      throw new Error(updateError.message);
    }
  }

  return {
    role: updates.role ?? existing.role,
    full_name: updates.full_name ?? existing.full_name,
  };
}
