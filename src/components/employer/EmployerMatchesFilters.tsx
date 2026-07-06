"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { Job, MatchStatus } from "@/lib/types";

const statusFilters: { value: "all" | MatchStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "suggested", label: "New" },
  { value: "candidate_interested", label: "Interested" },
  { value: "employer_shortlisted", label: "Shortlisted" },
  { value: "mutual_fit", label: "Mutual fit" },
  { value: "rejected", label: "Passed" },
];

export function EmployerMatchesFilters({ jobs }: { jobs: Pick<Job, "id" | "title">[] }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeStatus = searchParams.get("status") ?? "all";
  const activeJob = searchParams.get("job") ?? "all";

  function updateParams(next: { status?: string; job?: string }) {
    const params = new URLSearchParams(searchParams.toString());

    if (next.status !== undefined) {
      if (next.status === "all") params.delete("status");
      else params.set("status", next.status);
    }

    if (next.job !== undefined) {
      if (next.job === "all") params.delete("job");
      else params.set("job", next.job);
    }

    const query = params.toString();
    router.push(query ? `/employer/matches?${query}` : "/employer/matches");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {statusFilters.map((filter) => (
          <button
            key={filter.value}
            type="button"
            onClick={() => updateParams({ status: filter.value })}
            className={`rounded-full px-4 py-2 text-sm font-medium transition ${
              activeStatus === filter.value
                ? "bg-foreground text-background"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {jobs.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="job-filter" className="text-sm font-medium text-muted-foreground">
            Role
          </label>
          <select
            id="job-filter"
            value={activeJob}
            onChange={(event) => updateParams({ job: event.target.value })}
            className="rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground"
          >
            <option value="all">All roles</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
