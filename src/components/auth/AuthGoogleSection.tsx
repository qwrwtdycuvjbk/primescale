"use client";

import { useState } from "react";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { ErrorBanner } from "@/components/site/form";
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleGoogleSignIn() {
    setLoading(true);
    setError("");

    const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!googleClientId) {
      setLoading(false);
      setError("Google sign-in is not enabled. Please sign in with email and password.");
      return;
    }

    try {
      const destination = encodeURIComponent(
        mode === "signup" ? "/auth/redirect" : (next ?? "/auth/redirect"),
      );
      const redirectUri = encodeURIComponent(`${window.location.origin}/auth/callback?next=${destination}&role=${role}`);
      const googleOAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${googleClientId}&redirect_uri=${redirectUri}&response_type=code&scope=openid%20email%20profile&prompt=select_account`;
      window.location.assign(googleOAuthUrl);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Google sign-in failed. Try again.",
      );
      setLoading(false);
    }
  }

  return (
    <>
      <div className={`flex items-center gap-2.5 ${compact ? "my-2.5" : "my-3"}`}>
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground sm:text-sm">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>

      {error && <ErrorBanner message={error} />}

      <GoogleSignInButton
        onClick={() => void handleGoogleSignIn()}
        disabled={loading}
        label={loading ? "Redirecting to Google..." : "Continue with Google"}
        compact={compact}
      />
    </>
  );
}
