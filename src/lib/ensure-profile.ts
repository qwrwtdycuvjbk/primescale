import type { SupabaseClient, User } from "@supabase/supabase-js";
import { getServiceClient } from "@/lib/supabase/service";
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
  if (role === "employer" || role === "candidate" || role === "admin") {
    return role;
  }
  return "candidate";
}

export function isAdminEmail(email: string | undefined) {
  if (!email) return false;
  const allowlist =
    process.env.ADMIN_EMAILS?.split(",")
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean) ?? [];
  return allowlist.includes(email.toLowerCase());
}

export function preferredRoleFromUser(user: User): UserRole | null {
  const role = user.user_metadata?.role;
  if (role === "employer" || role === "candidate" || role === "admin") {
    return role;
  }
  if (isAdminEmail(user.email)) {
    return "admin";
  }
  return null;
}

function resolveRole(user: User, preferredRole?: UserRole | null): UserRole {
  return normalizeRole(preferredRole ?? preferredRoleFromUser(user));
}

function isDuplicateKeyError(error: { code?: string; message?: string }) {
  return error.code === "23505" || error.message?.includes("profiles_pkey");
}

async function loadProfile(
  supabase: SupabaseClient,
  userId: string,
): Promise<{ role: string; full_name: string } | null> {
  const { data: profile } = await supabase
    .from("profiles")
    .select("role, full_name")
    .eq("id", userId)
    .maybeSingle();

  return profile;
}

async function loadProfileWithService(userId: string) {
  const service = getServiceClient();
  if (!service) return null;

  const { data: profile } = await service
    .from("profiles")
    .select("role, full_name")
    .eq("id", userId)
    .maybeSingle();

  return profile;
}

async function upsertProfileWithService(user: User, role: UserRole) {
  const service = getServiceClient();
  if (!service) return null;

  const fullName = profileNameFromUser(user);
  const phone =
    typeof user.user_metadata?.phone === "string"
      ? user.user_metadata.phone
      : null;

  const { data: profile, error } = await service
    .from("profiles")
    .upsert(
      {
        id: user.id,
        role,
        full_name: fullName,
        email: user.email ?? "",
        ...(phone ? { phone } : {}),
      },
      { onConflict: "id" },
    )
    .select("role, full_name")
    .maybeSingle();

  if (error) {
    throw new Error(error.message);
  }

  return profile;
}

async function recoverProfileWithService(user: User, role: UserRole) {
  const existing = await loadProfileWithService(user.id);
  if (existing) return existing;
  return upsertProfileWithService(user, role);
}

export async function ensureProfileForUser(
  supabase: SupabaseClient,
  user: User,
  preferredRole?: UserRole | null,
) {
  const existing = await loadProfile(supabase, user.id);
  if (existing) {
    const phone =
      typeof user.user_metadata?.phone === "string"
        ? user.user_metadata.phone
        : null;

    const updates: { role?: UserRole; full_name?: string; phone?: string } =
      {};
    if (isAdminEmail(user.email)) {
      updates.role = "admin";
    } else {
      const resolvedRole = preferredRole ?? preferredRoleFromUser(user);
      if (
        resolvedRole === "employer" ||
        resolvedRole === "candidate" ||
        resolvedRole === "admin"
      ) {
        if (existing.role === "admin" && resolvedRole !== "admin") {
          // Keep admin access once granted.
        } else {
          updates.role = resolvedRole;
        }
      }
    }
    if (!existing.full_name) {
      updates.full_name = profileNameFromUser(user);
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

  const { error: rpcError } = await supabase.rpc("ensure_user_profile", {
    p_role: preferredRole ?? preferredRoleFromUser(user),
  });

  if (!rpcError) {
    const profile = await loadProfile(supabase, user.id);
    if (profile) return profile;
  }

  const fullName = profileNameFromUser(user);
  const role = resolveRole(user, preferredRole);
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
    if (isDuplicateKeyError(insertError)) {
      const profile = await loadProfile(supabase, user.id);
      if (profile) return profile;

      const recovered = await recoverProfileWithService(user, role);
      if (recovered) return recovered;

      throw new Error(
        "Your account profile exists but could not be loaded. Sign out and try again.",
      );
    }

    throw new Error(insertError.message);
  }

  return { role, full_name: fullName };
}
