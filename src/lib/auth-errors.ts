export const authErrorMessages: Record<string, string> = {
  confirmation_failed: "Google sign-in could not be completed.",
  session_missing: "Your session expired. Please log in again.",
  profile_missing: "We could not set up your account profile.",
  missing_code:
    "Google did not return a sign-in code. Check Supabase redirect URLs.",
};

export function formatAuthErrorMessage(
  error: string | null | undefined,
  details?: string | null,
) {
  if (!error || !authErrorMessages[error]) return null;
  return details
    ? `${authErrorMessages[error]} (${details})`
    : authErrorMessages[error];
}

export function authLoginPathWithError(
  error: string,
  details?: string,
  role?: "employer" | "candidate" | null,
) {
  const base =
    role === "employer"
      ? "/auth/employer/login"
      : role === "candidate"
        ? "/auth/candidate/login"
        : "/auth/login";
  const params = new URLSearchParams({ error });
  if (details) params.set("details", details);
  return `${base}?${params.toString()}`;
}
