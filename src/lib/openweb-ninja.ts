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
  /** Google-for-Jobs locale used for this result (us, gb, …) */
  sourceLocale: string | null;
};

const BASE_URL = "https://api.openwebninja.com/jsearch";

const DEFAULT_QUERIES = [
  "software engineer remote UK",
  "full stack developer remote UK",
  "backend engineer remote London",
  "frontend engineer remote United Kingdom",
  "devops engineer remote UK",
];

/**
 * JSearch defaults country to "us" when omitted. For worldwide we fan out
 * across a few English-friendly locales (keeps API calls bounded).
 */
const WORLDWIDE_COUNTRIES = ["gb"] as const;

/** Appended to the query so non-US locales aren't flooded by US postings */
const COUNTRY_QUERY_HINT: Record<string, string> = {
  us: "United States",
  gb: "United Kingdom",
  ie: "Ireland",
  au: "Australia",
  nl: "Netherlands",
  de: "Germany",
  ca: "Canada",
  se: "Sweden",
  pt: "Portugal",
  sg: "Singapore",
  fr: "France",
  es: "Spain",
};

/** Max leads kept per locale on worldwide searches so US doesn't dominate */
const MAX_LEADS_PER_LOCALE = 8;

/** Roles that only accept US / North America candidates */
const US_ONLY_MARKERS = [
  /\bus\s*only\b/i,
  /\busa\s*only\b/i,
  /\bunited\s+states\s+only\b/i,
  /\bmust\s+be\s+(located\s+)?in\s+the\s+(us|u\.s\.|usa|united\s+states)\b/i,
  /\bmust\s+reside\s+in\s+the\s+(us|u\.s\.|usa|united\s+states)\b/i,
  /\bonly\s+(open\s+to\s+)?(candidates\s+)?(in|from)\s+the\s+(us|u\.s\.|usa|united\s+states)\b/i,
  /\b(us|u\.s\.|usa)\s+(based|located)\s+(candidates?|applicants?)\s+only\b/i,
  /\bcandidates?\s+must\s+be\s+(us|u\.s\.|usa)\s+(based|citizens?|residents?)\b/i,
  /\bmust\s+have\s+(the\s+)?(right|authorization)\s+to\s+work\s+in\s+the\s+(us|u\.s\.|usa)\b/i,
  /\bno\s+(international|overseas|remote\s+outside)\b/i,
  /\b(north\s+america|united\s+states)\s+only\b/i,
];

const GLOBAL_REMOTE_MARKERS = [
  /\bworldwide\b/i,
  /\banywhere\b/i,
  /\binternational\b/i,
  /\bglobal(ly)?\b/i,
  /\bremote\s+(from\s+)?anywhere\b/i,
  /\bwork\s+from\s+anywhere\b/i,
  /\bopen\s+to\s+(all\s+)?(countries|locations|time\s*zones)\b/i,
];

/**
 * Hide spam aggregators + staffing / recruiting firms as the employer.
 * Real companies that post on LinkedIn / Indeed / Glassdoor should still show.
 */
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
  /^board\s*jobs?/i,
  /^bebee$/i,
  /^jooble$/i,
  // Named staffing / recruiting firms
  /^jobot$/i,
  /^cybercoders$/i,
  /^robert\s*half/i,
  /^teksystems$/i,
  /^apex\s*systems$/i,
  /^insight\s*global$/i,
  /^randstad/i,
  /^manpower(group)?$/i,
  /^hays$/i,
  /^michael\s*page$/i,
  /^kforce$/i,
  /^modis$/i,
  /^allegis/i,
  /^aerotek$/i,
  /^actalent$/i,
  /^collabera$/i,
  /^cognizant$/i,
  /^accenture$/i,
  /^infosys$/i,
  /^tcs$|^tata\s*consultancy/i,
  /^wipro$/i,
  /^capgemini$/i,
  /^epam(\s*systems)?$/i,
  /^mindlance$/i,
  /^motion\s*recruitment/i,
  /^harvey\s*nash/i,
  /^hcl(\s*tech)?$/i,
  /^ltimindtree$/i,
  /^hexaware$/i,
  /^persistent\s*systems$/i,
  /^globant$/i,
  /^softserve$/i,
  /^endava$/i,
  /^grid\s*dynamics$/i,
  /^people\s*prime$/i,
  // Generic staffing / recruiting employer names
  /staffing/i,
  /recruit(ing|ers?|ment)/i,
  /talent\s*(solutions?|partners?|agency|group)/i,
  /personnel/i,
  /workforce\s*solutions?/i,
  /\brpo\b/i,
  /contract\s*(staffing|recruit)/i,
  /it\s*(staffing|recruit)/i,
  /tech(nology)?\s*(staffing|recruit)/i,
];

/** Only spam mills / staffing publishers — keep LinkedIn, Indeed, etc. */
const BLOCKED_PUBLISHERS = [
  "Vacancy Target Jobs",
  "vacancy target jobs",
  "VacancyGlobal",
  "Careerhubs.pro",
  "Remote Jobs USA",
  "BoardJobs",
  "Board Jobs",
  "BeBee",
  "Jooble",
  "Jobot",
  "CyberCoders",
  "Robert Half",
  "TEKsystems",
  "Apex Systems",
  "Insight Global",
  "Kforce",
  "Actalent",
  "Collabera",
];

const FAKE_DESCRIPTION_MARKERS = [
  /reputed company/i,
  /our reputed company/i,
];

/** Phrases that usually mean a staffing agency is posting for a client */
const STAFFING_DESCRIPTION_MARKERS = [
  /our\s+client\s+is\s+(looking|seeking|hiring)/i,
  /on\s+behalf\s+of\s+(our\s+)?(client|customer)/i,
  /staffing\s+(agency|firm|company)/i,
  /recruiting\s+(agency|firm|company)/i,
  /we\s+are\s+a\s+(leading\s+)?(it\s+)?staffing/i,
  /contract\s+to\s+hire\s+opportunity\s+with\s+(our\s+)?client/i,
  /working\s+with\s+(one\s+of\s+)?our\s+(end\s+)?clients?/i,
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

function isBlockedPublisher(publisher: string) {
  const normalized = publisher.trim().toLowerCase();
  if (!normalized) return false;
  return BLOCKED_PUBLISHERS.some(
    (blocked) => blocked.toLowerCase() === normalized,
  );
}

function isStaffingLead(job: OpenWebNinjaJob) {
  const company = job.employer_name ?? "";
  if (
    BLOCKED_EMPLOYER_PATTERNS.some((pattern) => pattern.test(company.trim()))
  ) {
    return true;
  }

  const description = job.job_description ?? "";
  return STAFFING_DESCRIPTION_MARKERS.some((pattern) =>
    pattern.test(description),
  );
}

function jobText(job: OpenWebNinjaJob) {
  return [job.job_title, job.job_description, job.job_city, job.job_state]
    .filter(Boolean)
    .join(" ");
}

/** US state / territory abbreviations often returned as job_state */
const US_STATE_CODES = new Set([
  "al", "ak", "az", "ar", "ca", "co", "ct", "dc", "de", "fl", "ga", "hi", "ia",
  "id", "il", "in", "ks", "ky", "la", "ma", "md", "me", "mi", "mn", "mo", "ms",
  "mt", "nc", "nd", "ne", "nh", "nj", "nm", "nv", "ny", "oh", "ok", "or", "pa",
  "ri", "sc", "sd", "tn", "tx", "ut", "va", "vt", "wa", "wi", "wv", "wy",
]);

const US_LOCATION_MARKERS = [
  /\bunited\s+states\b/i,
  /\bUSA\b/,
  /\bU\.S\.A\.?\b/,
  /\b(remote\s+)?(us|u\.s\.)\s*(-|–|—)?\s*(based|only|remote)?\b/i,
  /\b(new\s+york|san\s+francisco|los\s+angeles|seattle|austin|boston|chicago|denver|atlanta|miami)\b/i,
];

const UK_MARKERS = [
  /\bUK\b/,
  /\bU\.K\.?\b/,
  /\bunited\s+kingdom\b/i,
  /\bgreat\s+britain\b/i,
  /\bbritain\b/i,
  /\bengland\b/i,
  /\bscotland\b/i,
  /\bwales\b/i,
  /\bnorthern\s+ireland\b/i,
  /\blondon\b/i,
  /\bmanchester\b/i,
  /\bbirmingham\b/i,
  /\bledinburgh\b/i,
  /\bbristol\b/i,
  /\bleeds\b/i,
  /\bglasgow\b/i,
  /\b£\d/,
  /\bGBP\b/,
  /\bsterling\b/i,
];

const LOCALE_MARKERS: Record<string, RegExp[]> = {
  gb: UK_MARKERS,
  ie: [/\bIreland\b/i, /\bDublin\b/i, /\b€\d/, /\bEUR\b/],
  au: [
    /\bAustralia\b/i,
    /\bSydney\b/i,
    /\bMelbourne\b/i,
    /\bBrisbane\b/i,
    /\bA\$\d/,
    /\bAUD\b/,
  ],
  ca: [/\bCanada\b/i, /\bToronto\b/i, /\bVancouver\b/i, /\bCAD\b/],
  nl: [/\bNetherlands\b/i, /\bAmsterdam\b/i, /\bDutch\b/i, /\b€\d/],
  de: [/\bGermany\b/i, /\bBerlin\b/i, /\bMunich\b/i, /\b€\d/, /\bEUR\b/],
};

function matchesLocale(job: OpenWebNinjaJob, locale: string) {
  const markers = LOCALE_MARKERS[locale];
  if (!markers?.length) return true;
  const blob = [
    job.job_title,
    job.job_description,
    job.job_city,
    job.job_state,
    job.job_country,
    job.employer_name,
  ]
    .filter(Boolean)
    .join(" ");
  return markers.some((pattern) => pattern.test(blob));
}

function isUsOnlyRestricted(job: OpenWebNinjaJob) {
  return US_ONLY_MARKERS.some((pattern) => pattern.test(jobText(job)));
}

function isUsCountryCode(value: string | null | undefined) {
  if (!value) return false;
  const normalized = value.trim().toLowerCase();
  return (
    normalized === "us" ||
    normalized === "usa" ||
    normalized === "united states" ||
    normalized === "united states of america"
  );
}

/** True when the posting is clearly a US-market / US-based role */
function looksUsBasedJob(job: OpenWebNinjaJob) {
  if (isUsCountryCode(job.job_country)) return true;
  if (isUsOnlyRestricted(job)) return true;

  const state = job.job_state?.trim().toLowerCase() ?? "";
  if (state && US_STATE_CODES.has(state)) return true;

  const locationBlob = [job.job_city, job.job_state, job.job_country, job.job_title]
    .filter(Boolean)
    .join(" ");
  if (US_LOCATION_MARKERS.some((pattern) => pattern.test(locationBlob))) {
    return true;
  }

  return false;
}

function isUsefulLead(
  job: OpenWebNinjaJob,
  options?: { excludeUsJobs?: boolean; requireLocale?: string },
) {
  if (!hasRealCompanyName(job.employer_name)) return false;
  if (!job.job_is_remote) return false;
  if (isStaffingLead(job)) return false;

  const publisher = job.job_publisher?.trim() ?? "";
  if (isBlockedPublisher(publisher)) return false;

  const description = job.job_description ?? "";
  const fakeHits = FAKE_DESCRIPTION_MARKERS.reduce(
    (count, pattern) => count + (description.match(pattern)?.length ?? 0),
    0,
  );
  // Spam mills paste "reputed company" many times
  if (fakeHits >= 2) return false;

  if (options?.excludeUsJobs && looksUsBasedJob(job)) return false;

  // API often returns null country — require local keywords (UK, London, £, …)
  if (
    options?.requireLocale &&
    options.requireLocale !== "us" &&
    !matchesLocale(job, options.requireLocale)
  ) {
    return false;
  }

  return true;
}

function resolveCountries(countryRaw: string): string[] {
  if (!countryRaw || countryRaw === "worldwide" || countryRaw === "all") {
    return [...WORLDWIDE_COUNTRIES];
  }
  return [countryRaw];
}

function localizeQuery(query: string, country: string) {
  const hint = COUNTRY_QUERY_HINT[country];
  if (!hint) return query;
  const lower = query.toLowerCase();
  if (
    lower.includes(hint.toLowerCase()) ||
    (country === "gb" && (lower.includes(" uk") || lower.includes("britain")))
  ) {
    return query;
  }
  if (country === "us") {
    return `${query} remote`;
  }
  // JSearch recommends title + location in the query string
  return `${query} in ${hint}`;
}

function toLead(
  job: OpenWebNinjaJob,
  sourceLocale: string,
): RemoteTechJobLead {
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
    sourceLocale,
  };
}

export async function searchRemoteTechJobs(options?: {
  query?: string;
  queries?: string[];
  datePosted?: "today" | "3days" | "week" | "month" | "all";
  /** ISO country code, or "worldwide" / empty for multi-locale remote search */
  country?: string;
  pages?: number;
}): Promise<{
  ok: true;
  leads: RemoteTechJobLead[];
  queriesUsed: string[];
  countriesUsed: string[];
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
  const countryRaw = options?.country?.trim().toLowerCase() ?? "worldwide";
  const isWorldwide =
    !countryRaw || countryRaw === "worldwide" || countryRaw === "all";
  const countries = resolveCountries(countryRaw);
  const pages = Math.min(Math.max(options?.pages ?? 1, 1), 3);

  const byLocale = new Map<string, RemoteTechJobLead[]>();
  const seenIds = new Set<string>();
  const queriesUsed: string[] = [];

  for (const query of queries) {
    for (const country of countries) {
      const localizedQuery = localizeQuery(query, country);
      if (!queriesUsed.includes(localizedQuery)) {
        queriesUsed.push(localizedQuery);
      }

      const params = new URLSearchParams({
        query: localizedQuery,
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

      const excludeUsJobs = country !== "us";
      const bucket = byLocale.get(country) ?? [];
      for (const job of jobs) {
        if (!job?.job_id || !job.job_title || !job.employer_name) continue;
        if (seenIds.has(job.job_id)) continue;
        if (
          !isUsefulLead(job, {
            excludeUsJobs,
            requireLocale: country,
          })
        ) {
          continue;
        }
        seenIds.add(job.job_id);
        bucket.push(toLead(job, country));
      }
      byLocale.set(country, bucket);
    }
  }

  const leads: RemoteTechJobLead[] = [];
  for (const country of countries) {
    const bucket = byLocale.get(country) ?? [];
    const capped = isWorldwide
      ? bucket.slice(0, MAX_LEADS_PER_LOCALE)
      : bucket;
    leads.push(...capped);
  }

  leads.sort((a, b) => {
    // Prefer non-US posting country, then non-US search locale, then global wording, then newest
    const aUsJob = isUsCountryCode(a.country) ? 1 : 0;
    const bUsJob = isUsCountryCode(b.country) ? 1 : 0;
    if (aUsJob !== bUsJob) return aUsJob - bUsJob;

    const aUsLocale = a.sourceLocale === "us" ? 1 : 0;
    const bUsLocale = b.sourceLocale === "us" ? 1 : 0;
    if (aUsLocale !== bUsLocale) return aUsLocale - bUsLocale;

    const aText = `${a.title} ${a.descriptionPreview}`;
    const bText = `${b.title} ${b.descriptionPreview}`;
    const aGlobal = GLOBAL_REMOTE_MARKERS.some((p) => p.test(aText)) ? 1 : 0;
    const bGlobal = GLOBAL_REMOTE_MARKERS.some((p) => p.test(bText)) ? 1 : 0;
    if (bGlobal !== aGlobal) return bGlobal - aGlobal;

    const aTime = a.postedAt ? Date.parse(a.postedAt) : 0;
    const bTime = b.postedAt ? Date.parse(b.postedAt) : 0;
    return bTime - aTime;
  });

  return {
    ok: true,
    leads,
    queriesUsed: queries.length === 1 ? queriesUsed : queries,
    countriesUsed: countries,
  };
}
