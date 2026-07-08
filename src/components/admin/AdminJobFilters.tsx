"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { EXPERIENCE_LEVELS, ROLE_TYPES } from "@/lib/constants";
import type { JobStatus } from "@/lib/types";

const JOB_STATUSES: { value: "all" | JobStatus; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
  { value: "paused", label: "Paused" },
  { value: "closed", label: "Closed" },
  { value: "archived", label: "Archived" },
];

export function AdminJobFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const search = searchParams.get("q") ?? "";
  const status = searchParams.get("status") ?? "all";
  const experience = searchParams.get("experience") ?? "all";
  const roleType = searchParams.get("role_type") ?? "all";

  function updateParams(updates: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString());

    for (const [key, value] of Object.entries(updates)) {
      if (!value || value === "all") params.delete(key);
      else params.set(key, value);
    }

    const query = params.toString();
    router.push(query ? `/admin/jobs?${query}` : "/admin/jobs");
  }

  const selectClass =
    "rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground";

  return (
    <div className="space-y-4 rounded-3xl border border-border bg-card p-5">
      <div>
        <label htmlFor="job-search" className="text-sm font-medium text-muted-foreground">
          Search
        </label>
        <input
          id="job-search"
          type="search"
          defaultValue={search}
          placeholder="Role title, company, or employer email"
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
          <label htmlFor="filter-status" className="text-sm font-medium text-muted-foreground">
            Status
          </label>
          <select
            id="filter-status"
            className={`mt-2 w-full ${selectClass}`}
            value={status}
            onChange={(event) => updateParams({ status: event.target.value })}
          >
            {JOB_STATUSES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
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
            className={`mt-2 w-full ${selectClass}`}
            value={experience}
            onChange={(event) => updateParams({ experience: event.target.value })}
          >
            <option value="all">All levels</option>
            {EXPERIENCE_LEVELS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="filter-role-type" className="text-sm font-medium text-muted-foreground">
            Role type
          </label>
          <select
            id="filter-role-type"
            className={`mt-2 w-full ${selectClass}`}
            value={roleType}
            onChange={(event) => updateParams({ role_type: event.target.value })}
          >
            <option value="all">All types</option>
            {ROLE_TYPES.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {(search || status !== "all" || experience !== "all" || roleType !== "all") && (
        <button
          type="button"
          onClick={() => router.push("/admin/jobs")}
          className="text-sm font-medium text-muted-foreground underline hover:text-foreground"
        >
          Clear all filters
        </button>
      )}
    </div>
  );
}
