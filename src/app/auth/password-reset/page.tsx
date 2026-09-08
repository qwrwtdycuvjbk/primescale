"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { AuthShell } from "@/components/auth/AuthShell";
import { djangoAuth } from "@/lib/api/auth";
import { ErrorBanner, PrimaryButton } from "@/components/site/form";
import { fieldInputClass, fieldLabelClass } from "@/components/site/form-styles";

export default function PasswordResetPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;

    setLoading(true);
    setError("");

    try {
      await djangoAuth.requestPasswordReset(email.trim().toLowerCase());
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send reset link. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password."
      description="Enter your email to receive a secure link to set or reset your password."
    >
      <div className="w-full">
        {submitted ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <p className="text-sm">
                If an account exists for <strong>{email}</strong>, a password reset link has been dispatched.
              </p>
            </div>
            <p className="text-xs text-muted-foreground">
              Please check your inbox (and spam folder) for instructions. The link will expire in 24 hours.
            </p>
            <div className="pt-2">
              <Link
                href="/auth/login"
                className="inline-flex items-center gap-2 text-sm font-medium text-foreground hover:text-primary"
              >
                Return to log in
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className={fieldLabelClass}>
                Account Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className={`${fieldInputClass} py-2 text-sm`}
              />
            </div>

            {error && <ErrorBanner message={error} />}

            <PrimaryButton
              type="submit"
              disabled={loading}
              className="relative z-10 w-full cursor-pointer py-2.5 text-sm"
            >
              {loading ? "Sending link..." : "Send reset link"}
              <ArrowRight className="h-4 w-4" />
            </PrimaryButton>

            <p className="mt-3 text-center text-xs text-muted-foreground sm:text-sm">
              Remembered your password?{" "}
              <Link href="/auth/login" className="font-medium text-foreground hover:text-primary">
                Log in
              </Link>
            </p>
          </form>
        )}
      </div>
    </AuthShell>
  );
}
