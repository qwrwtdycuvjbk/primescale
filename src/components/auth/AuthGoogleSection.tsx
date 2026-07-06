"use client";

import { useState } from "react";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { ErrorBanner } from "@/components/site/form";
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function getOAuthRedirectUrl() {
    const destination = encodeURIComponent(
      mode === "signup" ? "/auth/redirect" : (next ?? "/auth/redirect"),
    );
    return `${window.location.origin}/auth/callback?next=${destination}&role=${role}`;
  }

  async function handleGoogleSignIn() {
    setLoading(true);
    setError("");

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
      setLoading(false);
      setError("Sign-in is not configured. Missing Supabase environment variables.");
      return;
    }

    try {
      const supabase = createClient();
      const { data, error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: getOAuthRedirectUrl(),
          queryParams: {
            prompt: "select_account",
          },
        },
      });

      if (oauthError) {
        setError(oauthError.message);
        setLoading(false);
        return;
      }

      if (data?.url) {
        window.location.assign(data.url);
        return;
      }

      setError(
        "Could not start Google sign-in. Enable Google in Supabase → Authentication → Providers.",
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Google sign-in failed. Try again.",
      );
    } finally {
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
