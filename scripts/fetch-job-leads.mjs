#!/usr/bin/env node
/**
 * Fetch remote tech job leads via OpenWeb Ninja (free tier friendly).
 *
 * Setup:
 * 1. Get a free key: https://app.openwebninja.com/api/jsearch
 * 2. Add OPENWEB_NINJA_API_KEY=... to .env.local
 * 3. Run: node scripts/fetch-job-leads.mjs
 *    Optional: node scripts/fetch-job-leads.mjs "devops engineer remote"
 */

import { readFileSync } from "fs";
import { resolve } from "path";

function loadEnvLocal() {
  try {
    const raw = readFileSync(resolve(process.cwd(), ".env.local"), "utf8");
    for (const line of raw.split("\n")) {
      const match = line.match(/^([^#=]+)=(.*)$/);
      if (!match) continue;
      const key = match[1].trim();
      const value = match[2].trim();
      if (!process.env[key]) process.env[key] = value;
    }
  } catch {
    // .env.local may not exist yet
  }
}

loadEnvLocal();

const apiKey = process.env.OPENWEB_NINJA_API_KEY?.trim();
if (!apiKey) {
  console.error(
    "Missing OPENWEB_NINJA_API_KEY.\nGet a free key at https://app.openwebninja.com/api/jsearch and add it to .env.local",
  );
  process.exit(1);
}

const query = process.argv[2] || "software engineer remote";
const params = new URLSearchParams({
  query,
  country: "us",
  date_posted: "3days",
  work_from_home: "true",
  employment_types: "FULLTIME,CONTRACTOR",
  num_pages: "1",
});

const response = await fetch(
  `https://api.openwebninja.com/jsearch/search-v2?${params}`,
  {
    headers: { "x-api-key": apiKey },
  },
);

const text = await response.text();
if (!response.ok) {
  console.error("Request failed:", response.status, text.slice(0, 500));
  process.exit(1);
}

const payload = JSON.parse(text);
const jobs = Array.isArray(payload.data)
  ? payload.data
  : Array.isArray(payload.data?.jobs)
    ? payload.data.jobs
    : [];

console.log(`Query: ${query}`);
console.log(`Results: ${jobs.length}\n`);

for (const job of jobs.slice(0, 15)) {
  console.log(`- ${job.job_title}`);
  console.log(`  Company: ${job.employer_name}`);
  console.log(`  Posted: ${job.job_posted_at || job.job_posted_at_datetime_utc || "n/a"}`);
  console.log(`  Apply: ${job.job_apply_link || "n/a"}`);
  console.log("");
}
