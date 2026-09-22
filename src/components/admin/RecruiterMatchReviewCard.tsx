"use client";

import Link from "next/link";
import type { Match } from "@/lib/types";

export function RecruiterMatchReviewCard({ match }: { match: Match }) {
  const candidate = match.candidate_profiles;
  const candidateId = candidate?.id || match.candidate_profile_id;
  const job = match.jobs;
  const name = candidate?.profiles?.full_name ?? "Candidate";

  return (
    <article className="rounded-3xl border border-border bg-card p-6 transition hover:border-border/80">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs uppercase tracking-widest text-primary font-bold">
              {match.match_score}% match fit
            </span>
            <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground capitalize">
              {match.status.replace("_", " ")}
            </span>
          </div>

          <h3 className="display-headline mt-2 text-2xl font-bold">
            {candidateId ? (
              <Link
                href={`/admin/candidates/${candidateId}`}
                className="hover:text-primary hover:underline"
              >
                {name}
              </Link>
            ) : (
              name
            )}
          </h3>

          <p className="mt-1 text-sm text-muted-foreground font-medium">
            Matched for: <span className="text-foreground">{job?.title ?? "Job Opportunity"}</span>
            {job?.companies?.name && (
              <span className="text-muted-foreground"> · {job.companies.name}</span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {candidateId && (
            <Link
              href={`/admin/candidates/${candidateId}`}
              className="rounded-full border border-border bg-background px-4 py-1.5 text-xs font-semibold text-foreground hover:bg-muted transition"
            >
              View Candidate Dossier
            </Link>
          )}
        </div>
      </div>

      {candidate && (
        <div className="mt-5 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3 pt-4 border-t border-border">
          <div>
            <span className="font-medium text-foreground block">Experience</span>
            <span className="capitalize">{candidate.experience_level ?? "—"} ({candidate.years_experience ?? 0} yrs)</span>
          </div>
          <div>
            <span className="font-medium text-foreground block">Location</span>
            <span>{candidate.us_state ?? "Remote"}</span>
          </div>
          <div>
            <span className="font-medium text-foreground block">Availability</span>
            <span className="capitalize">{candidate.availability_status?.replace("_", " ") ?? "—"}</span>
          </div>
        </div>
      )}

      {candidate?.skills && candidate.skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {candidate.skills.slice(0, 8).map((skill: string, index: number) => (
            <span
              key={index}
              className="rounded-full bg-muted/60 border border-border px-2.5 py-0.5 text-xs text-foreground"
            >
              {skill}
            </span>
          ))}
          {candidate.skills.length > 8 && (
            <span className="text-xs text-muted-foreground self-center">
              +{candidate.skills.length - 8} more
            </span>
          )}
        </div>
      )}
    </article>
  );
}
