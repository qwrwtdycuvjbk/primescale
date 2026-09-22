export const authErrorMessages: Record<string, string> = {
  confirmation_failed: "Google sign-in could not be completed.",
  session_missing: "Your session expired. Please log in again.",
  profile_missing: "We could not set up your account profile.",
  missing_code:
    "OAuth provider did not return an authorization code. Please try again.",
  oauth_cancelled: "Google sign-in was cancelled.",
  oauth_failed: "Google sign-in could not be completed. Please try again or use email and password.",
  oauth_misconfigured: "Google sign-in is currently unavailable. Please sign in with email and password.",
  validation: "Check the form and try again.",
  login_failed: "Could not sign you in.",
  signup_failed: "Could not create your account.",
  admin_unauthorized: "This account does not have administrator access.",
};

export function formatAuthErrorMessage(
  error: string | null | undefined,
  details?: string | null,
) {
  if (!error || !authErrorMessages[error]) return null;

  const detailText = details?.toLowerCase() ?? "";

  if (error === "admin_unauthorized") {
    return details || authErrorMessages.admin_unauthorized;
  }

  if (detailText.includes("denied by the admin") || detailText.includes("access is denied")) {
    return "Your access is denied by the Admin.";
  }

  if (error === "login_failed" && detailText.includes("email not confirmed")) {
    return "Confirm your email first. Check your inbox for the verification link, then log in.";
  }

  if (error === "signup_failed" && detailText.includes("already registered")) {
    return "An account with this email already exists. Log in instead, or use a different email.";
  }

  if (
    error === "profile_missing" &&
    detailText.includes("infinite recursion")
  ) {
    return "Account setup encountered a database policy error. Please try again or contact support.";
  }

  return details
    ? `${authErrorMessages[error]} (${details})`
    : authErrorMessages[error];
}

export function authLoginPathWithError(
  error: string,
  details?: string,
  role?: "employer" | "candidate" | "admin" | null,
) {
  const base =
    role === "employer"
      ? "/auth/employer/login"
      : role === "candidate"
        ? "/auth/candidate/login"
        : role === "admin"
          ? "/auth/admin/login"
          : "/auth/login";
  const params = new URLSearchParams({ error });
  if (details) params.set("details", details);
  return `${base}?${params.toString()}`;
}
