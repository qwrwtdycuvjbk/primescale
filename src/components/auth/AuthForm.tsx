import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AuthGoogleSection } from "@/components/auth/AuthGoogleSection";
import { submitAuth } from "@/lib/auth-actions";
import { formatAuthErrorMessage } from "@/lib/auth-errors";
import type { UserRole } from "@/lib/types";
import { ErrorBanner, PrimaryButton } from "@/components/site/form";
import { fieldInputClass, fieldLabelClass } from "@/components/site/form-styles";

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
  next,
  error,
  details,
  awaiting,
  email,
}: {
  mode: "login" | "signup";
  role: Extract<UserRole, "employer" | "candidate">;
  next?: string | null;
  error?: string | null;
  details?: string | null;
  awaiting?: string | null;
  email?: string | null;
}) {
  const copy = role === "employer" ? employerCopy : candidateCopy;
  const basePath = `/auth/${role}`;
  const isLogin = mode === "login";
  const compactInputClass = `${fieldInputClass} py-2 text-sm`;
  const authErrorMessage = formatAuthErrorMessage(error, details);

  if (awaiting) {
    return (
      <div className="w-full">
        <h2 className="display-headline text-4xl">Almost there.</h2>
        <p className="mt-3 text-muted-foreground">
          We sent a verification link to{" "}
          <strong className="text-foreground">{awaiting}</strong>. Click the link
          in that email to activate your account, then log in.
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

  if (isLogin) {
    return (
      <div className="w-full">
        <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted-foreground sm:text-xs">
          {role === "employer" ? "For employers" : "For candidates"}
        </p>
        <h2 className="display-headline mt-1 text-xl text-foreground sm:text-2xl">
          {copy.loginTitle}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground sm:text-sm">
          {copy.loginSubtitle}
        </p>

        <form action="/api/auth/login" method="post" className="mt-3 space-y-2.5">
          <input type="hidden" name="role" value={role} />
          {next ? <input type="hidden" name="next" value={next} /> : null}

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
              className={compactInputClass}
            />
          </div>

          {authErrorMessage && <ErrorBanner message={authErrorMessage} />}

          <PrimaryButton
            type="submit"
            className="relative z-10 w-full cursor-pointer py-2.5 text-sm"
          >
            Log in
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
        action={submitAuth}
        method="post"
        className={isLogin ? "mt-3 space-y-2.5" : "mt-4 space-y-3"}
      >
        <input type="hidden" name="mode" value={mode} />
        <input type="hidden" name="role" value={role} />
        {next ? <input type="hidden" name="next" value={next} /> : null}

        {mode === "signup" && (
          <div>
            <label htmlFor="fullName" className={fieldLabelClass}>
              Full name
            </label>
            <input
              id="fullName"
              name="fullName"
              type="text"
              required
              autoComplete="name"
              className={compactInputClass}
            />
          </div>
        )}

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
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className={compactInputClass}
          />
          {mode === "signup" && (
            <p className="mt-1 text-[11px] text-muted-foreground sm:text-xs">
              Minimum 8 characters. Email verification required.
            </p>
          )}
        </div>

        {mode === "signup" && (
          <div>
            <label htmlFor="phone" className={fieldLabelClass}>
              Phone (optional)
            </label>
            <input
              id="phone"
              name="phone"
              type="tel"
              autoComplete="tel"
              className={compactInputClass}
              placeholder="+1 (555) 000-0000"
            />
          </div>
        )}

        {authErrorMessage && <ErrorBanner message={authErrorMessage} />}

        <PrimaryButton
          type="submit"
          className={`relative z-10 w-full cursor-pointer ${isLogin ? "py-2.5 text-sm" : ""}`}
        >
          {mode === "signup" ? "Create account" : "Log in"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </form>

      <AuthGoogleSection mode={mode} role={role} next={next} compact={isLogin} />

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
