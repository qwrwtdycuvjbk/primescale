"use client";

import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { createClient } from "@/lib/supabase/client";
import type { UserRole } from "@/lib/types";

export function AuthGoogleSection({
  mode,
  role,
  next,
  compact,
}: {
  mode: "login" | "signup";
  role: Extract<UserRole, "employer" | "candidate">;
  next?: string | null;
  compact?: boolean;
}) {
  function getSignupNext() {
    return "/auth/redirect";
  }

  function getLoginNext() {
    return next ?? "/auth/redirect";
  }

  function getOAuthRedirectUrl() {
    const destination = encodeURIComponent(
      mode === "signup" ? getSignupNext() : getLoginNext(),
    );
    return `${window.location.origin}/auth/callback?next=${destination}&role=${role}`;
  }

  async function handleGoogleSignIn() {
    const supabase = createClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: getOAuthRedirectUrl(),
        queryParams: {
          prompt: "select_account",
        },
      },
    });
  }

  return (
    <>
      <div className={`flex items-center gap-2.5 ${compact ? "my-2.5" : "my-3"}`}>
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground sm:text-sm">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <GoogleSignInButton
        onClick={() => void handleGoogleSignIn()}
        compact={compact}
      />
    </>
  );
}
