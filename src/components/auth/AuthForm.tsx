"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ArrowRight } from "lucide-react";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { createClient } from "@/lib/supabase/client";
import type { UserRole } from "@/lib/types";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  fieldInputClass,
} from "@/components/site/form";

const employerCopy = {
  signupTitle: "Create your employer account",
  signupSubtitle: "Post US remote tech roles and get AI-matched candidates.",
  loginTitle: "Employer log in",
  loginSubtitle: "Manage roles, review matches, and shortlist candidates.",
  emailLabel: "Work email",
};

const candidateCopy = {
  signupTitle: "Create your candidate account",
  signupSubtitle: "Build your profile and get matched to US remote tech roles.",
  loginTitle: "Candidate log in",
  loginSubtitle: "Access your profile, matches, and dashboard.",
  emailLabel: "Email",
};

export function AuthForm({
  mode,
  role,
}: {
  mode: "login" | "signup";
  role: Extract<UserRole, "employer" | "candidate">;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  const [awaitingEmail, setAwaitingEmail] = useState(false);

  const copy = role === "employer" ? employerCopy : candidateCopy;
  const basePath = `/auth/${role}`;
  const isLogin = mode === "login";
  const compactInputClass = `${fieldInputClass} py-2 text-sm`;

  function getSignupNext() {
    return "/auth/redirect";
  }

  function getLoginNext() {
    return next ?? "/auth/redirect";
  }

  function getConfirmRedirectUrl() {
    const destination = encodeURIComponent(getSignupNext());
    return `${window.location.origin}/auth/confirm?next=${destination}&role=${role}`;
  }

  function getOAuthRedirectUrl() {
    const destination = encodeURIComponent(
      mode === "signup" ? getSignupNext() : getLoginNext(),
    );
    let url = `${window.location.origin}/auth/callback?next=${destination}`;
    if (mode === "signup") {
      url += `&role=${role}`;
    }
    return url;
  }

  async function savePhone(userId: string) {
    if (!phone.trim()) return;
    const supabase = createClient();
    await supabase.from("profiles").update({ phone: phone.trim() }).eq("id", userId);
  }

  async function handleGoogleSignIn() {
    setStatus("loading");
    setMessage("");

    const supabase = createClient();

    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: getOAuthRedirectUrl(),
        queryParams: {
          prompt: "select_account",
        },
      },
    });

    if (error) {
      setStatus("error");
      setMessage(error.message);
    }
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
          data: {
            role,
            full_name: fullName,
            phone: phone.trim() || undefined,
          },
          emailRedirectTo: getConfirmRedirectUrl(),
        },
      });

      if (error) {
        setStatus("error");
        setMessage(error.message);
        return;
      }

      if (data.session && data.user) {
        await savePhone(data.user.id);
        router.push(getSignupNext());
        router.refresh();
        return;
      }

      setAwaitingEmail(true);
      setStatus("idle");
      return;
    }

    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setStatus("error");
      setMessage(error.message);
      return;
    }

    if (data.user) {
      await savePhone(data.user.id);
    }

    router.push(getLoginNext());
    router.refresh();
  }

  const authError = searchParams.get("error");
  const authDetails = searchParams.get("details");

  const errorMessages: Record<string, string> = {
    confirmation_failed: "Google sign-in could not be completed.",
    session_missing: "Your session expired. Please log in again.",
    profile_missing: "We could not set up your account profile.",
    missing_code: "Google did not return a sign-in code. Check Supabase redirect URLs.",
  };

  if (awaitingEmail) {
    return (
      <div className="w-full">
        <h2 className="display-headline text-4xl">Almost there.</h2>
        <p className="mt-3 text-muted-foreground">
          We sent a verification link to <strong className="text-foreground">{email}</strong>.
          Click the link in that email to activate your account, then log in.
        </p>
        <Link
          href={`${basePath}/login`}
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
      <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground sm:text-xs">
        {role === "employer" ? "For employers" : "For candidates"}
      </p>
      <h2
        className={`display-headline mt-1 text-foreground ${
          isLogin ? "text-xl sm:text-2xl" : "text-2xl sm:text-3xl"
        }`}
      >
        {mode === "signup" ? copy.signupTitle : copy.loginTitle}
      </h2>
      <p
        className={`text-muted-foreground ${
          isLogin ? "mt-1 text-xs sm:text-sm" : "mt-2 text-sm sm:text-base"
        }`}
      >
        {mode === "signup" ? copy.signupSubtitle : copy.loginSubtitle}
      </p>

      <form
        onSubmit={handleSubmit}
        className={isLogin ? "mt-3 space-y-2.5" : "mt-4 space-y-3"}
      >
        {mode === "signup" && (
          <div>
            <FieldLabel htmlFor="fullName">Full name</FieldLabel>
            <input
              id="fullName"
              type="text"
              required
              className={compactInputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
        )}

        <div>
          <FieldLabel htmlFor="email">{copy.emailLabel}</FieldLabel>
          <input
            id="email"
            type="email"
            required
            className={compactInputClass}
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
            className={compactInputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {mode === "signup" && (
            <p className="mt-1 text-[11px] text-muted-foreground sm:text-xs">
              Minimum 8 characters. Email verification required.
            </p>
          )}
        </div>

        {mode === "signup" && (
          <div>
            <FieldLabel htmlFor="phone">Phone (optional)</FieldLabel>
            <input
              id="phone"
              type="tel"
              className={compactInputClass}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 (555) 000-0000"
            />
          </div>
        )}

        {authError && errorMessages[authError] && (
          <ErrorBanner
            message={
              authDetails
                ? `${errorMessages[authError]} (${authDetails})`
                : errorMessages[authError]
            }
          />
        )}

        {message && <ErrorBanner message={message} />}

        <PrimaryButton
          type="submit"
          disabled={status === "loading"}
          className={`w-full ${isLogin ? "py-2.5 text-sm" : ""}`}
        >
          {status === "loading"
            ? "Please wait..."
            : mode === "signup"
              ? "Create account"
              : "Log in"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </form>

      <div className={`flex items-center gap-2.5 ${isLogin ? "my-2.5" : "my-3"}`}>
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground sm:text-sm">or</span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <GoogleSignInButton
        onClick={handleGoogleSignIn}
        disabled={status === "loading"}
        compact={isLogin}
      />

      <p className={`text-center text-xs text-muted-foreground sm:text-sm ${isLogin ? "mt-3" : "mt-4"}`}>
        {mode === "signup" ? (
          <>
            Already have an account?{" "}
            <Link
              href={`${basePath}/login`}
              className="font-medium text-foreground hover:text-primary"
            >
              Log in
            </Link>
          </>
        ) : (
          <>
            New to PrimeScale?{" "}
            <Link
              href={`${basePath}/signup`}
              className="font-medium text-foreground hover:text-primary"
            >
              Create an account
            </Link>
            <span className="mx-1.5 text-border">·</span>
            {role === "employer" ? (
              <>
                <Link
                  href="/auth/candidate/login"
                  className="font-medium text-foreground hover:text-primary"
                >
                  Candidate log in
                </Link>
              </>
            ) : (
              <>
                <Link
                  href="/auth/employer/login"
                  className="font-medium text-foreground hover:text-primary"
                >
                  Employer log in
                </Link>
              </>
            )}
          </>
        )}
      </p>

      {mode === "signup" && (
        <p className="mt-2 text-center text-xs text-muted-foreground sm:text-sm">
          {role === "employer" ? (
            <>
              Looking for a job?{" "}
              <Link
                href="/auth/candidate/signup"
                className="font-medium text-foreground hover:text-primary"
              >
                Candidate signup
              </Link>
            </>
          ) : (
            <>
              Hiring?{" "}
              <Link
                href="/auth/employer/signup"
                className="font-medium text-foreground hover:text-primary"
              >
                Employer signup
              </Link>
            </>
          )}
        </p>
      )}
    </div>
  );
}
