"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Match, MatchStatus } from "@/lib/types";
import { PrimaryButton, SecondaryButton } from "@/components/site/form";

export function CandidateMatchCard({ match }: { match: Match }) {
  const [status, setStatus] = useState(match.status);
  const [loading, setLoading] = useState(false);

  async function updateStatus(newStatus: MatchStatus) {
    setLoading(true);
    try {
      const response = await fetch("/api/matches", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ matchId: match.id, status: newStatus }),
      });
      if (response.ok) {
        const data = (await response.json()) as { status?: MatchStatus };
        setStatus(data.status ?? newStatus);
      }
    } finally {
      setLoading(false);
    }
  }

  const job = match.jobs;

  return (
    <article className="rounded-3xl border border-border bg-card p-6 transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-primary">
            {match.match_score}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">
            {job?.title ?? "Role"}
          </h3>
          {job?.companies?.name && (
            <p className="mt-1 text-sm text-muted-foreground">
              {job.companies.name}
            </p>
          )}
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize text-muted-foreground">
          {status.replace(/_/g, " ")}
        </span>
      </div>

      {match.match_reason && (
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {match.match_reason}
        </p>
      )}

      {job?.tech_stack && (
        <div className="mt-4 flex flex-wrap gap-2">
          {job.tech_stack.slice(0, 6).map((skill) => (
            <span
              key={skill}
              className="rounded-full border border-border px-3 py-1 text-xs text-foreground"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {status === "mutual_fit" && (
        <p className="mt-6 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-foreground">
          Mutual fit confirmed. People Prime will reach out to coordinate next
          steps with the employer.
        </p>
      )}

      {(status === "suggested" || status === "employer_shortlisted") && (
        <div className="mt-6 flex flex-wrap gap-3">
          <PrimaryButton
            type="button"
            disabled={loading}
            onClick={() => updateStatus("candidate_interested")}
          >
            I&apos;m interested
          </PrimaryButton>
          <SecondaryButton
            type="button"
            disabled={loading}
            onClick={() => updateStatus("rejected")}
          >
            Not for me
          </SecondaryButton>
        </div>
      )}
    </article>
  );
}

export function EmptyMatches({ editProfileHref }: { editProfileHref: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center">
      <p className="display-headline text-3xl">No matches yet</p>
      <p className="mx-auto mt-3 max-w-md text-muted-foreground">
        We scan active US tech roles against your profile. Make sure your skills
        and resume are up to date for better matching.
      </p>
      <Link href={editProfileHref} className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-foreground hover:text-primary">
        Update profile
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
