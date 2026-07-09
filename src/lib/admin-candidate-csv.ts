import {
  AVAILABILITY_OPTIONS,
  EXPERIENCE_LEVELS,
  PRIVACY_OPTIONS,
  ROLE_CATEGORIES,
  WORK_AUTH_OPTIONS,
  WORK_TYPE_OPTIONS,
} from "@/lib/constants";
import type { AdminCreateCandidateInput } from "@/lib/admin-create-candidate";
import type {
  AvailabilityStatus,
  ExperienceLevel,
  PreferredWorkType,
} from "@/lib/types";

export const CANDIDATE_IMPORT_TEMPLATE_PATH =
  "/templates/people-prime-candidate-import.xlsx";

export const CANDIDATE_IMPORT_TEMPLATE_CSV_PATH =
  "/templates/people-prime-candidate-import.csv";

const HEADER_MAP: Record<string, keyof AdminCreateCandidateInput | "location"> = {
  full_name: "fullName",
  fullname: "fullName",
  name: "fullName",
  email: "email",
  phone: "phone",
  headline: "headline",
  current_title: "currentTitle",
  currenttitle: "currentTitle",
  title: "currentTitle",
  years_experience: "yearsExperience",
  yearsexperience: "yearsExperience",
  experience_years: "yearsExperience",
  skills: "skills",
  role_categories: "roleCategories",
  rolecategories: "roleCategories",
  categories: "roleCategories",
  experience_level: "experienceLevel",
  experiencelevel: "experienceLevel",
  level: "experienceLevel",
  salary_min: "salaryMin",
  salarymin: "salaryMin",
  salary_max: "salaryMax",
  salarymax: "salaryMax",
  work_authorization: "workAuthorization",
  workauthorization: "workAuthorization",
  work_auth: "workAuthorization",
  location: "location",
  us_state: "location",
  state: "location",
  preferred_work_type: "preferredWorkType",
  preferredworktype: "preferredWorkType",
  work_type: "preferredWorkType",
  availability: "availabilityStatus",
  availability_status: "availabilityStatus",
  bio: "bio",
  linkedin_url: "linkedinUrl",
  linkedin: "linkedinUrl",
  github_url: "githubUrl",
  github: "githubUrl",
  portfolio_url: "portfolioUrl",
  portfolio: "portfolioUrl",
  resume_url: "resumeUrl",
  resume: "resumeUrl",
};

type ParsedRow = Record<string, string>;

export type CsvImportRowResult =
  | { row: number; ok: true; email: string; matchesCreated: number }
  | { row: number; ok: false; email: string; error: string };

function normalizeHeader(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

/** Minimal RFC-style CSV parser (quoted fields, commas). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (inQuotes) {
      if (char === '"' && next === '"') {
        field += '"';
        i += 1;
      } else if (char === '"') {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || (char === "\r" && next === "\n")) {
      row.push(field);
      field = "";
      if (row.some((cell) => cell.trim())) rows.push(row);
      row = [];
      if (char === "\r") i += 1;
    } else if (char !== "\r") {
      field += char;
    }
  }

  row.push(field);
  if (row.some((cell) => cell.trim())) rows.push(row);

  return rows;
}

function splitList(value: string) {
  return value
    .split(/[|;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseExperienceLevel(value: string): ExperienceLevel {
  const normalized = value.trim().toLowerCase();
  if (EXPERIENCE_LEVELS.some((level) => level.value === normalized)) {
    return normalized as ExperienceLevel;
  }
  if (/junior|jr|0-2/.test(normalized)) return "junior";
  if (/senior|sr|6\+/.test(normalized)) return "senior";
  if (/lead|staff|principal/.test(normalized)) return "lead";
  return "mid";
}

function parseWorkAuth(value: string) {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, "_");
  if (WORK_AUTH_OPTIONS.some((option) => option.value === normalized)) {
    return normalized;
  }
  if (normalized.includes("international") || normalized.includes("global")) {
    return "international_remote";
  }
  if (normalized.includes("citizen")) return "us_citizen";
  if (normalized.includes("green")) return "green_card";
  if (normalized.includes("h1")) return "h1b";
  if (normalized.includes("ead") || normalized.includes("opt")) return "ead";
  return "international_remote";
}

function parseAvailability(value: string): AvailabilityStatus {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, "_");
  if (AVAILABILITY_OPTIONS.some((option) => option.value === normalized)) {
    return normalized as AvailabilityStatus;
  }
  if (normalized.includes("not")) return "not_looking";
  if (normalized.includes("open")) return "open";
  return "actively_looking";
}

function parseWorkType(value: string): PreferredWorkType {
  const normalized = value.trim().toLowerCase();
  if (WORK_TYPE_OPTIONS.some((option) => option.value === normalized)) {
    return normalized as PreferredWorkType;
  }
  if (normalized.includes("hybrid")) return "hybrid";
  if (normalized.includes("onsite") || normalized.includes("on-site")) return "onsite";
  return "remote";
}

function mapRow(headers: string[], cells: string[]): ParsedRow {
  const row: ParsedRow = {};
  headers.forEach((header, index) => {
    const key = HEADER_MAP[normalizeHeader(header)];
    if (!key) return;
    row[key] = (cells[index] ?? "").trim();
  });
  return row;
}

function matchRoleCategories(values: string[]) {
  const normalized = values.map((v) => v.toLowerCase());
  return ROLE_CATEGORIES.filter((category) =>
    normalized.some(
      (value) =>
        category.toLowerCase() === value ||
        category.toLowerCase().includes(value) ||
        value.includes(category.toLowerCase()),
    ),
  );
}

export function csvRowToCandidateInput(row: ParsedRow): AdminCreateCandidateInput {
  const roleCategoryValues = splitList(row.roleCategories ?? "");
  const matchedCategories =
    roleCategoryValues.length > 0 ? matchRoleCategories(roleCategoryValues) : [];

  const yearsRaw = row.yearsExperience?.trim();
  const salaryMinRaw = row.salaryMin?.trim();
  const salaryMaxRaw = row.salaryMax?.trim();

  return {
    fullName: row.fullName ?? "",
    email: row.email ?? "",
    phone: row.phone || undefined,
    headline: row.headline ?? "",
    currentTitle: row.currentTitle || undefined,
    yearsExperience: yearsRaw ? Number(yearsRaw) : undefined,
    skills: row.skills ?? "",
    roleCategories: matchedCategories.length
      ? [...matchedCategories]
      : roleCategoryValues,
    experienceLevel: parseExperienceLevel(row.experienceLevel ?? "mid"),
    salaryMin: salaryMinRaw ? Number(salaryMinRaw) : undefined,
    salaryMax: salaryMaxRaw ? Number(salaryMaxRaw) : undefined,
    workAuthorization: parseWorkAuth(row.workAuthorization ?? "international_remote"),
    usState: row.location?.trim() || "Remote",
    preferredWorkType: parseWorkType(row.preferredWorkType ?? "remote"),
    availabilityStatus: parseAvailability(row.availabilityStatus ?? "actively_looking"),
    privacyVisibility: "employers_only",
    bio: row.bio || undefined,
    githubUrl: row.githubUrl || undefined,
    portfolioUrl: row.portfolioUrl || undefined,
    linkedinUrl: row.linkedinUrl || undefined,
    resumeUrl: row.resumeUrl || undefined,
    source: "people_prime",
  };
}

export function validateCandidateImportRow(
  input: AdminCreateCandidateInput,
  rowNumber: number,
): string | null {
  if (!input.fullName.trim()) return `Row ${rowNumber}: full_name is required`;
  if (!input.email.trim() || !input.email.includes("@")) {
    return `Row ${rowNumber}: valid email is required`;
  }
  if (!input.headline.trim()) return `Row ${rowNumber}: headline is required`;
  if (!input.skills.trim()) return `Row ${rowNumber}: skills is required`;
  if (input.roleCategories.length === 0) {
    return `Row ${rowNumber}: role_categories must match at least one category (${ROLE_CATEGORIES.join(", ")})`;
  }
  if (
    input.yearsExperience != null &&
    Number.isNaN(input.yearsExperience)
  ) {
    return `Row ${rowNumber}: years_experience must be a number`;
  }
  if (!PRIVACY_OPTIONS.some((option) => option.value === input.privacyVisibility)) {
    return `Row ${rowNumber}: invalid privacy setting`;
  }
  return null;
}

export function parseCandidateImportGrid(grid: string[][]) {
  const headerIndex = grid.findIndex((row) => {
    const normalized = row.map((cell) => normalizeHeader(String(cell ?? "")));
    return normalized.includes("email") && normalized.includes("full_name");
  });

  if (headerIndex === -1) {
    return {
      rows: [] as { rowNumber: number; input: AdminCreateCandidateInput }[],
      error:
        "Could not find a header row with full_name and email. Use the Excel template.",
    };
  }

  const headerRow = grid[headerIndex].map((cell) => String(cell ?? ""));
  const dataRows = grid.slice(headerIndex + 1);
  const rows: { rowNumber: number; input: AdminCreateCandidateInput }[] = [];

  dataRows.forEach((cells, index) => {
    const rowNumber = headerIndex + index + 2;
    const stringCells = cells.map((cell) => String(cell ?? "").trim());
    const firstCell = stringCells[0] ?? "";
    if (!firstCell || firstCell.startsWith("#")) return;
    if (stringCells.every((cell) => !cell)) return;

    const parsed = mapRow(headerRow, stringCells);
    if (!parsed.email && !parsed.fullName) return;

    rows.push({ rowNumber, input: csvRowToCandidateInput(parsed) });
  });

  if (rows.length === 0) {
    return {
      rows: [],
      error: "No candidate rows found. Add rows under the header in the Candidates sheet.",
    };
  }

  return { rows, error: null as string | null };
}

export function parseCandidateImportCsv(text: string) {
  const grid = parseCsv(text.trim());
  if (grid.length < 2) {
    return {
      rows: [] as { rowNumber: number; input: AdminCreateCandidateInput }[],
      error: "File must include a header row and at least one candidate.",
    };
  }

  return parseCandidateImportGrid(grid);
}

export async function parseCandidateImportFile(file: File) {
  const name = file.name.toLowerCase();

  if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
    const { read, utils } = await import("xlsx");
    const buffer = await file.arrayBuffer();
    const workbook = read(buffer, { type: "array" });
    const sheetName =
      workbook.SheetNames.find((title) =>
        title.toLowerCase().includes("candidate"),
      ) ?? workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];
    const grid = utils.sheet_to_json<(string | number)[]>(sheet, {
      header: 1,
      defval: "",
      raw: false,
    }) as string[][];
    return parseCandidateImportGrid(grid);
  }

  const text = await file.text();
  return parseCandidateImportCsv(text);
}
