/**
 * Google Search Console verification code (meta tag content value only).
 * Set GOOGLE_SITE_VERIFICATION in Vercel, or paste the code below as a fallback.
 */
export const GOOGLE_SITE_VERIFICATION_FALLBACK = "";

export function getGoogleSiteVerification(): string | undefined {
  const fromEnv = process.env.GOOGLE_SITE_VERIFICATION?.trim();
  if (fromEnv) return fromEnv;

  const fallback = GOOGLE_SITE_VERIFICATION_FALLBACK.trim();
  return fallback || undefined;
}
