"use client";

import { useRouter, useSearchParams } from "next/navigation";
import {
  AVAILABILITY_OPTIONS,
  CANDIDATE_SOURCE_OPTIONS,
  EXPERIENCE_LEVELS,
  WORK_AUTH_OPTIONS,
} from "@/lib/constants";

export function AdminCandidateFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const search = searchParams.get("q") ?? "";
  const complete = searchParams.get("complete") ?? "all";
  const availability = searchParams.get("availability") ?? "all";
  const experience = searchParams.get("experience") ?? "all";
  const workAuth = searchParams.get("work_auth") ?? "all";
  const matching = searchParams.get("matching") ?? "all";
  const resume = searchParams.get("resume") ?? "all";
  const source = searchParams.get("source") ?? "all";

  function updateParams(updates: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString());

    for (const [key, value] of Object.entries(updates)) {
      if (!value || value === "all") params.delete(key);
      else params.set(key, value);
    }

    const query = params.toString();
    router.push(query ? `/admin/candidates?${query}` : "/admin/candidates");
  }

  const selectClass =
    "rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground";

  return (
    <div className="space-y-4 rounded-3xl border border-border bg-card p-5">
      <div>
        <label htmlFor="candidate-search" className="text-sm font-medium text-muted-foreground">
          Search
        </label>
        <input
          id="candidate-search"
          type="search"
          defaultValue={search}
          placeholder="Name or email"
          className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              updateParams({ q: event.currentTarget.value.trim() || undefined });
            }
          }}
        />
        <p className="mt-1 text-xs text-muted-foreground">Press Enter to search</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor="filter-complete" className="text-sm font-medium text-muted-foreground">
            Profile
          </label>
          <select
            id="filter-complete"
            value={complete}
            onChange={(event) => updateParams({ complete: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All profiles</option>
            <option value="yes">Complete</option>
            <option value="no">Incomplete</option>
          </select>
        </div>

        <div>
          <label htmlFor="filter-availability" className="text-sm font-medium text-muted-foreground">
            Availability
          </label>
          <select
            id="filter-availability"
            value={availability}
            onChange={(event) => updateParams({ availability: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All</option>
            {AVAILABILITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filter-experience" className="text-sm font-medium text-muted-foreground">
            Experience
          </label>
          <select
            id="filter-experience"
            value={experience}
            onChange={(event) => updateParams({ experience: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All levels</option>
            {EXPERIENCE_LEVELS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filter-work-auth" className="text-sm font-medium text-muted-foreground">
            Work authorization
          </label>
          <select
            id="filter-work-auth"
            value={workAuth}
            onChange={(event) => updateParams({ work_auth: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All</option>
            {WORK_AUTH_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filter-matching" className="text-sm font-medium text-muted-foreground">
            Open to matching
          </label>
          <select
            id="filter-matching"
            value={matching}
            onChange={(event) => updateParams({ matching: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All</option>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </select>
        </div>

        <div>
          <label htmlFor="filter-resume" className="text-sm font-medium text-muted-foreground">
            Resume
          </label>
          <select
            id="filter-resume"
            value={resume}
            onChange={(event) => updateParams({ resume: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All</option>
            <option value="yes">Uploaded</option>
            <option value="no">Missing</option>
          </select>
        </div>

        <div>
          <label htmlFor="filter-source" className="text-sm font-medium text-muted-foreground">
            Source
          </label>
          <select
            id="filter-source"
            value={source}
            onChange={(event) => updateParams({ source: event.target.value })}
            className={`${selectClass} mt-2 w-full`}
          >
            <option value="all">All sources</option>
            {CANDIDATE_SOURCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(search ||
        complete !== "all" ||
        availability !== "all" ||
        experience !== "all" ||
        workAuth !== "all" ||
        matching !== "all" ||
        resume !== "all" ||
        source !== "all") && (
        <button
          type="button"
          onClick={() => router.push("/admin/candidates")}
          className="text-sm font-medium text-primary hover:opacity-80"
        >
          Clear all filters
        </button>
      )}
    </div>
  );
}
