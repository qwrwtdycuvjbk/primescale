"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRight } from "lucide-react";
import { createClient } from "@/lib/supabase/client";
import type { UserRole } from "@/lib/types";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  fieldInputClass,
} from "@/components/site/form";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const role = (searchParams.get("role") as UserRole) || "candidate";
  const next = searchParams.get("next");

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  const [awaitingEmail, setAwaitingEmail] = useState(false);

  function getDefaultNext() {
    return role === "employer" ? "/employer/onboarding" : "/candidate/onboarding";
  }

  function getConfirmRedirectUrl() {
    const destination = encodeURIComponent(next ?? getDefaultNext());
    return `${window.location.origin}/auth/confirm?next=${destination}`;
  }

  async function handleOAuth(provider: "google" | "linkedin") {
    const supabase = createClient();
    const redirectTo = `${window.location.origin}/auth/confirm?next=${encodeURIComponent(
      next ?? getDefaultNext(),
    )}`;

    await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo,
      },
    });
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setMessage("");

    const supabase = createClient();

    if (mode === "signup") {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { role, full_name: fullName },
          emailRedirectTo: getConfirmRedirectUrl(),
        },
      });

      if (error) {
        setStatus("error");
        setMessage(error.message);
        return;
      }

      if (data.session) {
        router.push(next ?? getDefaultNext());
        router.refresh();
        return;
      }

      setAwaitingEmail(true);
      setStatus("idle");
      return;
    }

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setStatus("error");
      setMessage(error.message);
      return;
    }

    router.push(next ?? "/auth/redirect");
    router.refresh();
  }

  const isEmployer = role === "employer";
  const confirmError = searchParams.get("error");

  if (awaitingEmail) {
    return (
      <div className="w-full">
        <h2 className="display-headline text-4xl">Almost there.</h2>
        <p className="mt-3 text-muted-foreground">
          We sent a verification link to <strong className="text-foreground">{email}</strong>.
          Click the link in that email to activate your account, then log in.
        </p>
        <p className="mt-4 text-sm text-muted-foreground">
          If the button in the email does not work, copy the full link from the email
          and paste it into your browser. Check spam if you do not see it.
        </p>
        <Link
          href={`/auth/login?role=${role}`}
          className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-foreground hover:text-primary"
        >
          Go to log in
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    );
  }

  return (
    <div className="w-full">
      <h2 className="display-headline text-4xl">
        {mode === "signup"
          ? isEmployer
            ? "Employer signup"
            : "Candidate signup"
          : "Welcome back"}
      </h2>
      <p className="mt-3 text-muted-foreground">
        {mode === "signup"
          ? isEmployer
            ? "Post US remote tech roles and get AI-matched candidates."
            : "Build your profile and get matched to US remote tech roles."
          : "Access your PrimeScale dashboard."}
      </p>

      {mode === "signup" && (
        <div className="mt-6 flex rounded-full border border-border p-1">
          <Link
            href="/auth/signup?role=employer"
            className={`flex-1 rounded-full px-4 py-2 text-center text-sm font-medium transition ${
              isEmployer
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Employer
          </Link>
          <Link
            href="/auth/signup?role=candidate"
            className={`flex-1 rounded-full px-4 py-2 text-center text-sm font-medium transition ${
              !isEmployer
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Candidate
          </Link>
        </div>
      )}

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => handleOAuth("google")}
          className="rounded-xl border border-border px-4 py-3 text-sm font-medium transition-colors hover:bg-muted"
        >
          Continue with Google
        </button>
        <button
          type="button"
          onClick={() => handleOAuth("linkedin")}
          className="rounded-xl border border-border px-4 py-3 text-sm font-medium transition-colors hover:bg-muted"
        >
          Continue with LinkedIn
        </button>
      </div>

      <div className="my-8 flex items-center gap-4">
        <span className="h-px flex-1 bg-border" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          or email
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {mode === "signup" && (
          <div>
            <FieldLabel htmlFor="fullName">Full name</FieldLabel>
            <input
              id="fullName"
              type="text"
              required
              className={fieldInputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
        )}

        <div>
          <FieldLabel htmlFor="email">Work email</FieldLabel>
          <input
            id="email"
            type="email"
            required
            className={fieldInputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            className={fieldInputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Minimum 8 characters. Email verification required.
          </p>
        </div>

        {confirmError === "confirmation_failed" && (
          <ErrorBanner message="Email confirmation failed or expired. Sign up again or request a new link from Supabase." />
        )}

        {message && <ErrorBanner message={message} />}

        <PrimaryButton
          type="submit"
          disabled={status === "loading"}
          className="w-full"
        >
          {status === "loading"
            ? "Please wait..."
            : mode === "signup"
              ? "Create account"
              : "Log in"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        {mode === "signup" ? (
          <>
            Already have an account?{" "}
            <Link
              href={`/auth/login?role=${role}`}
              className="font-medium text-foreground hover:text-primary"
            >
              Log in
            </Link>
          </>
        ) : (
          <>
            New to PrimeScale?{" "}
            <Link
              href={`/auth/signup?role=${role}`}
              className="font-medium text-foreground hover:text-primary"
            >
              Create an account
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
