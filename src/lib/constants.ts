export const ROLE_CATEGORIES = [
  "AI / ML",
  "Cloud",
  "Data",
  "DevOps",
  "Cybersecurity",
  "Full-stack",
  "Backend",
  "Frontend",
  "Mobile",
] as const;

export const EXPERIENCE_LEVELS = [
  { value: "junior", label: "Junior (0–2 years)" },
  { value: "mid", label: "Mid (3–5 years)" },
  { value: "senior", label: "Senior (6+ years)" },
  { value: "lead", label: "Lead / Staff" },
] as const;

export const ROLE_TYPES = [
  { value: "contract", label: "Contract" },
  { value: "c2h", label: "Contract-to-hire" },
  { value: "full-time", label: "Full-time" },
] as const;

export const WORK_AUTH_OPTIONS = [
  { value: "us_citizen", label: "US citizen" },
  { value: "green_card", label: "Green card" },
  { value: "h1b", label: "H-1B (needs sponsorship)" },
  { value: "ead", label: "EAD / OPT" },
  { value: "other", label: "Other US work authorization" },
] as const;

export const AVAILABILITY_OPTIONS = [
  { value: "actively_looking", label: "Actively looking" },
  { value: "open", label: "Open to opportunities" },
  { value: "not_looking", label: "Not looking" },
] as const;

export const WORK_TYPE_OPTIONS = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
] as const;

export const PRIVACY_OPTIONS = [
  { value: "public", label: "Public" },
  { value: "employers_only", label: "Employers only" },
  { value: "invite_only", label: "Invite only" },
] as const;

export const INDUSTRIES = [
  "Software / SaaS",
  "Fintech",
  "Healthcare / Healthtech",
  "E-commerce",
  "Cybersecurity",
  "AI / ML",
  "Consulting",
  "Other",
] as const;

export const JOB_STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "closed", label: "Closed" },
  { value: "archived", label: "Archived" },
] as const;

export const US_STATES = [
  "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
  "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
  "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
  "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
  "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
  "DC", "Remote (US)",
] as const;
