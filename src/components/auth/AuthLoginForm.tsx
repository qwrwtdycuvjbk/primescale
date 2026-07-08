"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { formatAuthErrorMessage } from "@/lib/auth-errors";
import type { UserRole } from "@/lib/types";
import { ErrorBanner, PrimaryButton } from "@/components/site/form";
import { fieldInputClass, fieldLabelClass } from "@/components/site/form-styles";

const employerCopy = {
  loginTitle: "Employer log in",
  loginSubtitle: "Manage roles, review matches, and shortlist candidates.",
  emailLabel: "Work email",
};

const candidateCopy = {
  loginTitle: "Candidate log in",
  loginSubtitle: "Access your profile, matches, and dashboard.",
  emailLabel: "Email",
};

export function AuthLoginForm({
  role,
  next,
  error,
  details,
  email,
}: {
  role: Extract<UserRole, "employer" | "candidate">;
  next?: string | null;
  error?: string | null;
  details?: string | null;
  email?: string | null;
}) {
  const copy = role === "employer" ? employerCopy : candidateCopy;
  const basePath = `/auth/${role}`;
  const compactInputClass = `${fieldInputClass} py-2 text-sm`;
  const initialError = formatAuthErrorMessage(error, details);
  const [message, setMessage] = useState<string | null>(initialError);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage(null);

    const form = event.currentTarget;
    const formData = new FormData(form);
    const loginEmail = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    if (!loginEmail || !password) {
      setMessage("Enter your email and password.");
      setLoading(false);
      return;
    }

    const supabase = createClient();
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: loginEmail,
      password,
    });

    if (signInError) {
      setMessage(signInError.message);
      setLoading(false);
      return;
    }

    const response = await fetch("/api/auth/complete-login", { method: "POST" });
    const payload = (await response.json()) as { redirect?: string; error?: string };

    if (!response.ok || !payload.redirect) {
      setMessage(payload.error ?? "Sign-in succeeded but could not continue.");
      setLoading(false);
      return;
    }

    window.location.href = next && !isAdminRedirect(payload.redirect) ? next : payload.redirect;
  }

  return (
    <div className="w-full">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
        {role === "employer" ? "For employers" : "For candidates"}
      </p>
      <h2 className="display-headline mt-1 text-xl text-foreground sm:text-2xl">
        {copy.loginTitle}
      </h2>
      <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
        {copy.loginSubtitle}
      </p>

      <form onSubmit={(event) => void handleSubmit(event)} className="mt-3 space-y-2.5">
        <div>
          <label htmlFor="email" className={fieldLabelClass}>
            {copy.emailLabel}
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            defaultValue={email ?? ""}
            disabled={loading}
            className={compactInputClass}
          />
        </div>

        <div>
          <label htmlFor="password" className={fieldLabelClass}>
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={8}
            autoComplete="current-password"
            disabled={loading}
            className={compactInputClass}
          />
        </div>

        {message && <ErrorBanner message={message} />}

        <PrimaryButton
          type="submit"
          disabled={loading}
          className="relative z-10 w-full cursor-pointer py-2.5 text-sm"
        >
          {loading ? "Signing in..." : "Log in"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </form>

      <p className="mt-3 text-center text-xs text-muted-foreground sm:text-sm">
        New to PrimeScale?{" "}
        <Link
          href={`${basePath}/signup`}
          className="font-medium text-foreground hover:text-primary"
        >
          Create an account
        </Link>
        <span className="mx-1.5 text-border">·</span>
        {role === "employer" ? (
          <Link
            href="/auth/candidate/login"
            className="font-medium text-foreground hover:text-primary"
          >
            Candidate log in
          </Link>
        ) : (
          <Link
            href="/auth/employer/login"
            className="font-medium text-foreground hover:text-primary"
          >
            Employer log in
          </Link>
        )}
      </p>
    </div>
  );
}

function isAdminRedirect(path: string) {
  return path.startsWith("/admin");
}
