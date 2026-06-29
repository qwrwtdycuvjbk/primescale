"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { createClient } from "@/lib/supabase/client";
import type { UserRole } from "@/lib/types";
import { buttonPrimaryClass, inputClass, labelClass } from "@/lib/ui";

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

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setMessage("");

    const supabase = createClient();

    if (mode === "signup") {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { role, full_name: fullName },
          emailRedirectTo: `${window.location.origin}/auth/callback?next=${next ?? `/${role}`}`,
        },
      });

      if (error) {
        setStatus("error");
        setMessage(error.message);
        return;
      }

      const destination =
        next ?? (role === "employer" ? "/employer/onboarding" : "/candidate/onboarding");
      router.push(destination);
      router.refresh();
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

  return (
    <div className="mx-auto w-full max-w-md">
      <p className="text-sm font-semibold uppercase tracking-widest text-teal-600">
        {mode === "signup" ? "Create account" : "Welcome back"}
      </p>
      <h1 className="mt-3 text-3xl font-bold text-slate-900">
        {mode === "signup"
          ? isEmployer
            ? "Sign up as an employer"
            : "Sign up as a candidate"
          : "Log in to PrimeScale"}
      </h1>
      <p className="mt-3 text-slate-600">
        {mode === "signup"
          ? isEmployer
            ? "Post US remote tech roles and get AI-matched candidates."
            : "Build your profile and get matched to US remote tech roles."
          : "Access your PrimeScale dashboard."}
      </p>

      {mode === "signup" && (
        <div className="mt-6 flex rounded-full border border-slate-200 p-1">
          <Link
            href="/auth/signup?role=employer"
            className={`flex-1 rounded-full px-4 py-2 text-center text-sm font-medium transition ${
              isEmployer
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Employer
          </Link>
          <Link
            href="/auth/signup?role=candidate"
            className={`flex-1 rounded-full px-4 py-2 text-center text-sm font-medium transition ${
              !isEmployer
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Candidate
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        {mode === "signup" && (
          <div>
            <label htmlFor="fullName" className={labelClass}>
              Full name
            </label>
            <input
              id="fullName"
              type="text"
              required
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
        )}

        <div>
          <label htmlFor="email" className={labelClass}>
            Work email
          </label>
          <input
            id="email"
            type="email"
            required
            className={inputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="password" className={labelClass}>
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            className={inputClass}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {message && (
          <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
            {message}
          </p>
        )}

        <button
          type="submit"
          disabled={status === "loading"}
          className={`${buttonPrimaryClass} w-full`}
        >
          {status === "loading"
            ? "Please wait..."
            : mode === "signup"
              ? "Create account"
              : "Log in"}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600">
        {mode === "signup" ? (
          <>
            Already have an account?{" "}
            <Link
              href={`/auth/login?role=${role}`}
              className="font-medium text-teal-600 hover:text-teal-500"
            >
              Log in
            </Link>
          </>
        ) : (
          <>
            New to PrimeScale?{" "}
            <Link
              href={`/auth/signup?role=${role}`}
              className="font-medium text-teal-600 hover:text-teal-500"
            >
              Create an account
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
