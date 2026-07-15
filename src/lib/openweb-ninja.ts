export type OpenWebNinjaJob = {
  job_id: string;
  job_title: string;
  employer_name: string;
  employer_website?: string | null;
  job_publisher?: string | null;
  job_apply_link?: string | null;
  job_description?: string | null;
  job_is_remote?: boolean;
  job_posted_at?: string | null;
  job_posted_at_datetime_utc?: string | null;
  job_country?: string | null;
  job_city?: string | null;
  job_state?: string | null;
  job_employment_type?: string | null;
};

export type RemoteTechJobLead = {
  id: string;
  title: string;
  company: string;
  companyWebsite: string | null;
  applyUrl: string | null;
  publisher: string | null;
  postedAt: string | null;
  country: string | null;
  location: string | null;
  employmentType: string | null;
  isRemote: boolean;
  descriptionPreview: string;
};

const BASE_URL = "https://api.openwebninja.com/jsearch";

const DEFAULT_QUERIES = [
  "software engineer remote",
  "full stack developer remote",
  "devops engineer remote",
  "backend engineer remote",
  "frontend engineer remote",
];

/** Aggregators / fake employers that don't help outreach */
const BLOCKED_EMPLOYER_PATTERNS = [
  /^vacancy\s*target/i,
  /^vacancy\s*global/i,
  /^onewaytechhubs$/i,
  /^confidential$/i,
  /^undisclosed$/i,
  /^n\/?a$/i,
  /^unknown$/i,
  /^hiring\s*now$/i,
  /^remote\s*jobs?\s*usa$/i,
  /^careerhubs?/i,
];

const BLOCKED_PUBLISHERS = [
  "Vacancy Target Jobs",
  "vacancy target jobs",
  "VacancyGlobal",
  "Careerhubs.pro",
  "Remote Jobs USA",
];

const FAKE_DESCRIPTION_MARKERS = [
  /reputed company/i,
  /our reputed company/i,
];

function getApiKey() {
  return process.env.OPENWEB_NINJA_API_KEY?.trim() || null;
}

function previewDescription(text: string | null | undefined, max = 280) {
  if (!text) return "";
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

function hasRealCompanyName(name: string | null | undefined) {
  if (!name) return false;
  const trimmed = name.trim();
  if (trimmed.length < 2) return false;
  if (BLOCKED_EMPLOYER_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return false;
  }
  // Generic placeholders like "Company Name" / "Hiring Company"
  if (/^(company(\s+name)?|hiring\s+company|employer)$/i.test(trimmed)) {
    return false;
  }
  return true;
}

function isUsefulLead(job: OpenWebNinjaJob) {
  if (!hasRealCompanyName(job.employer_name)) return false;

  const publisher = job.job_publisher?.trim() ?? "";
  if (
    publisher &&
    BLOCKED_PUBLISHERS.some(
      (blocked) => blocked.toLowerCase() === publisher.toLowerCase(),
    )
  ) {
    return false;
  }

  const description = job.job_description ?? "";
  const fakeHits = FAKE_DESCRIPTION_MARKERS.reduce(
    (count, pattern) => count + (description.match(pattern)?.length ?? 0),
    0,
  );
  // Spam mills paste "reputed company" many times
  if (fakeHits >= 2) return false;

  return true;
}

function toLead(job: OpenWebNinjaJob): RemoteTechJobLead {
  const location = [job.job_city, job.job_state, job.job_country]
    .filter(Boolean)
    .join(", ");

  return {
    id: job.job_id,
    title: job.job_title,
    company: job.employer_name,
    companyWebsite: job.employer_website ?? null,
    applyUrl: job.job_apply_link ?? null,
    publisher: job.job_publisher ?? null,
    postedAt: job.job_posted_at_datetime_utc ?? job.job_posted_at ?? null,
    country: job.job_country ?? null,
    location: location || null,
    employmentType: job.job_employment_type ?? null,
    isRemote: Boolean(job.job_is_remote),
    descriptionPreview: previewDescription(job.job_description),
  };
}

export async function searchRemoteTechJobs(options?: {
  query?: string;
  queries?: string[];
  datePosted?: "today" | "3days" | "week" | "month" | "all";
  country?: string;
  pages?: number;
}): Promise<{
  ok: true;
  leads: RemoteTechJobLead[];
  queriesUsed: string[];
} | {
  ok: false;
  error: string;
  status: number;
}> {
  const apiKey = getApiKey();
  if (!apiKey) {
    return {
      ok: false,
      error:
        "OPENWEB_NINJA_API_KEY is not set. Get a free key at https://app.openwebninja.com/api/jsearch and add it to .env.local",
      status: 503,
    };
  }

  const queries =
    options?.query && options.query.trim()
      ? [options.query.trim()]
      : options?.queries?.length
        ? options.queries
        : DEFAULT_QUERIES;

  const datePosted = options?.datePosted ?? "3days";
  const country = options?.country ?? "us";
  const pages = Math.min(Math.max(options?.pages ?? 1, 1), 3);

  const byId = new Map<string, RemoteTechJobLead>();

  for (const query of queries) {
    const params = new URLSearchParams({
      query,
      country,
      date_posted: datePosted,
      work_from_home: "true",
      employment_types: "FULLTIME,CONTRACTOR",
      num_pages: String(pages),
      exclude_job_publishers: BLOCKED_PUBLISHERS.join(","),
    });

    const response = await fetch(`${BASE_URL}/search-v2?${params}`, {
      headers: {
        "x-api-key": apiKey,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const body = await response.text();
      return {
        ok: false,
        error: `OpenWeb Ninja error (${response.status}): ${body.slice(0, 300)}`,
        status: response.status,
      };
    }

    const payload = (await response.json()) as {
      status?: string;
      data?: OpenWebNinjaJob[] | { jobs?: OpenWebNinjaJob[] };
    };

    const jobs = Array.isArray(payload.data)
      ? payload.data
      : payload.data && Array.isArray(payload.data.jobs)
        ? payload.data.jobs
        : [];

    for (const job of jobs) {
      if (!job?.job_id || !job.job_title || !job.employer_name) continue;
      if (!isUsefulLead(job)) continue;
      byId.set(job.job_id, toLead(job));
    }
  }

  const leads = Array.from(byId.values()).sort((a, b) => {
    const aTime = a.postedAt ? Date.parse(a.postedAt) : 0;
    const bTime = b.postedAt ? Date.parse(b.postedAt) : 0;
    return bTime - aTime;
  });

  return { ok: true, leads, queriesUsed: queries };
}
