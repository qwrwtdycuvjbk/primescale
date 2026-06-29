const BLOCKED_SALARY_PHRASES = [
  "competitive",
  "doe",
  "negotiable",
  "based on experience",
  "commensurate",
  "tbd",
  "n/a",
];

export function isValidSalaryRange(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (normalized.length < 3) return false;
  if (BLOCKED_SALARY_PHRASES.some((p) => normalized === p || normalized.includes(p))) {
    return false;
  }
  return /\d/.test(normalized);
}

export function extractEmailDomain(email: string): string | null {
  const parts = email.split("@");
  if (parts.length !== 2) return null;
  return parts[1].toLowerCase();
}

export function extractWebsiteDomain(website: string): string | null {
  try {
    const url = website.startsWith("http") ? website : `https://${website}`;
    const host = new URL(url).hostname.toLowerCase();
    return host.replace(/^www\./, "");
  } catch {
    return null;
  }
}

export function isWorkEmailDomainVerified(
  workEmail: string,
  website?: string,
): boolean {
  if (!website?.trim()) return false;
  const emailDomain = extractEmailDomain(workEmail);
  const siteDomain = extractWebsiteDomain(website);
  if (!emailDomain || !siteDomain) return false;
  return emailDomain === siteDomain || emailDomain.endsWith(`.${siteDomain}`);
}

export function defaultJobExpiry(): string {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString();
}

export function isCompanyProfileComplete(company: {
  name?: string;
  size?: string | null;
  description?: string | null;
  hq_city?: string | null;
  industry?: string | null;
  profile_complete?: boolean;
} | null): boolean {
  if (!company) return false;
  if (company.profile_complete) return true;
  return Boolean(
    company.name?.trim() &&
      company.size &&
      company.description?.trim() &&
      company.hq_city?.trim() &&
      company.industry?.trim(),
  );
}
