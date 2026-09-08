"use client";

import { useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { AuthShell } from "@/components/auth/AuthShell";
import { djangoAuth } from "@/lib/api/auth";
import { ErrorBanner, PrimaryButton } from "@/components/site/form";
import { fieldInputClass, fieldLabelClass } from "@/components/site/form-styles";

export default function PasswordResetConfirmPage({
  searchParams,
}: {
  searchParams: Promise<{ uid?: string; token?: string }>;
}) {
  const router = useRouter();
  const params = use(searchParams);
  const uid = params.uid || "";
  const token = params.token || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password) return;

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await djangoAuth.confirmPasswordReset({
        uid,
        token,
        new_password: password,
      });
      setSuccess(true);
      setTimeout(() => {
        router.push("/auth/login");
      }, 2500);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Invalid or expired reset token. Please request a new link.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (!uid || !token) {
    return (
      <AuthShell
        title="Invalid Link"
        description="The password reset link is missing required parameters or is invalid."
      >
        <div className="space-y-4">
          <ErrorBanner message="This reset link is incomplete. Please request a new password reset." />
          <Link
            href="/auth/password-reset"
            className="inline-flex items-center gap-2 text-sm font-medium text-foreground hover:text-primary"
          >
            Request new reset link
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Set a new password."
      description="Enter your new password below to update your credentials and activate your account."
    >
      <div className="w-full">
        {success ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <p className="text-sm">
                Your password has been updated! Redirecting to login...
              </p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="password" className={fieldLabelClass}>
                New Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={`${fieldInputClass} py-2 text-sm`}
              />
            </div>

            <div>
              <label htmlFor="confirmPassword" className={fieldLabelClass}>
                Confirm New Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className={`${fieldInputClass} py-2 text-sm`}
              />
            </div>

            {error && <ErrorBanner message={error} />}

            <PrimaryButton
              type="submit"
              disabled={loading}
              className="relative z-10 w-full cursor-pointer py-2.5 text-sm"
            >
              {loading ? "Updating password..." : "Set new password"}
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>
          </form>
        )}
      </div>
    </AuthShell>
  );
}
