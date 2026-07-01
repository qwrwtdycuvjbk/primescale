"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { ensureProfileForUser } from "@/lib/ensure-profile";
import type { UserRole } from "@/lib/types";

function safeNextPath(next: string | null) {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return "/auth/redirect";
  }
  return next;
}

function redirectToLogin(error: string, details?: string) {
  const params = new URLSearchParams({ error });
  if (details) params.set("details", details);
  window.location.assign(`/auth/login?${params.toString()}`);
}

export function AuthCallbackClient() {
  const searchParams = useSearchParams();
  const [message, setMessage] = useState("Signing you in...");

  useEffect(() => {
    let cancelled = false;

    async function finish() {
      const supabase = createClient();
      const code = searchParams.get("code");
      const next = safeNextPath(searchParams.get("next"));
      const roleParam = searchParams.get("role");
      const preferredRole =
        roleParam === "employer" || roleParam === "candidate"
          ? (roleParam as UserRole)
          : null;

      if (code) {
        const { error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          if (!cancelled) {
            redirectToLogin("confirmation_failed", error.message);
          }
          return;
        }
      } else {
        const { data, error } = await supabase.auth.getSession();
        if (error || !data.session) {
          if (!cancelled) {
            redirectToLogin("session_missing", error?.message);
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
          redirectToLogin("session_missing", userError?.message);
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
          redirectToLogin("profile_missing", details);
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
