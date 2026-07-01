"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { ensureProfileForUser } from "@/lib/ensure-profile";
import { authLoginPathWithError } from "@/lib/auth-errors";
import { safeAuthNextPath } from "@/lib/supabase/auth-route";
import type { UserRole } from "@/lib/types";

function redirectToLogin(
  error: string,
  details?: string,
  role?: Extract<UserRole, "employer" | "candidate"> | null,
) {
  window.location.assign(authLoginPathWithError(error, details, role));
}

export function AuthCallbackClient() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState("Signing you in...");

  useEffect(() => {
    let cancelled = false;

    async function finish() {
      const supabase = createClient();
      const code = searchParams.get("code");
      const next = safeAuthNextPath(searchParams.get("next"));
      const roleParam = searchParams.get("role");
      const preferredRole: Extract<UserRole, "employer" | "candidate"> | null =
        roleParam === "employer" || roleParam === "candidate" ? roleParam : null;

      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          if (!cancelled) {
            redirectToLogin("confirmation_failed", error.message, preferredRole);
          }
          return;
        }
      } else {
        const { data, error } = await supabase.auth.getSession();
        if (error || !data.session) {
          if (!cancelled) {
            redirectToLogin("session_missing", error?.message, preferredRole);
          }
          return;
        }
      }

      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        if (!cancelled) {
          redirectToLogin("session_missing", userError?.message, preferredRole);
        }
        return;
      }

      try {
        await ensureProfileForUser(supabase, user, preferredRole);
      } catch (profileError) {
        if (!cancelled) {
          const details =
            profileError instanceof Error
              ? profileError.message
              : "Could not create profile";
          redirectToLogin("profile_missing", details, preferredRole);
        }
        return;
      }

      if (!cancelled) {
        setMessage("Redirecting...");
        window.location.assign(next);
      }
    }

    finish();

    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <p className="text-sm text-muted-foreground">{message}</p>
    </main>
  );
}
