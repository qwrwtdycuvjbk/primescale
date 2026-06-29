"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Job, Match, MatchStatus } from "@/lib/types";
import { PrimaryButton, SecondaryButton } from "@/components/site/form";

export function EmployerMatchCard({ match }: { match: Match }) {
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
      if (response.ok) setStatus(newStatus);
    } finally {
      setLoading(false);
    }
  }

  const candidate = match.candidate_profiles;
  const name = candidate?.profiles?.full_name ?? "Candidate";

  return (
    <article className="rounded-3xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-primary">
            {match.match_score}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">{name}</h3>
          {candidate?.headline && (
            <p className="mt-1 text-sm text-muted-foreground">{candidate.headline}</p>
          )}
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize">
          {status.replace(/_/g, " ")}
        </span>
      </div>
      {match.match_reason && (
        <p className="mt-4 text-sm text-muted-foreground">{match.match_reason}</p>
      )}
      {candidate?.skills && (
        <div className="mt-4 flex flex-wrap gap-2">
          {candidate.skills.slice(0, 8).map((skill) => (
            <span key={skill} className="rounded-full border border-border px-3 py-1 text-xs">
              {skill}
            </span>
          ))}
        </div>
      )}
      {status !== "rejected" && status !== "employer_shortlisted" && (
        <div className="mt-6 flex gap-3">
          <PrimaryButton type="button" disabled={loading} onClick={() => updateStatus("employer_shortlisted")}>
            Shortlist
          </PrimaryButton>
          <SecondaryButton type="button" disabled={loading} onClick={() => updateStatus("rejected")}>
            Pass
          </SecondaryButton>
        </div>
      )}
    </article>
  );
}

export function JobCard({ job }: { job: Job }) {
  const router = useRouter();
  const [status, setStatus] = useState(job.status);
  const [loading, setLoading] = useState(false);
  const [duplicating, setDuplicating] = useState(false);

  async function updateStatus(newStatus: string) {
    setLoading(true);
    const response = await fetch(`/api/jobs/${job.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });
    if (response.ok) setStatus(newStatus as Job["status"]);
    setLoading(false);
  }

  async function duplicate() {
    setDuplicating(true);
    try {
      const response = await fetch(`/api/jobs/${job.id}/duplicate`, {
        method: "POST",
      });
      if (response.ok) router.refresh();
    } finally {
      setDuplicating(false);
    }
  }

  return (
    <article className="rounded-3xl border border-border bg-card p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{job.title}</h3>
          <p className="mt-1 text-sm capitalize text-muted-foreground">{status}</p>
          {job.salary_range && (
            <p className="mt-2 text-sm text-muted-foreground">{job.salary_range}</p>
          )}
          {job.expires_at && (
            <p className="mt-1 text-xs text-muted-foreground">
              Expires {new Date(job.expires_at).toLocaleDateString()}
            </p>
          )}
        </div>
        {job.jd_quality_score != null && (
          <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            JD {job.jd_quality_score}%
          </span>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {status === "active" && (
          <SecondaryButton type="button" disabled={loading} onClick={() => updateStatus("paused")}>
            Pause
          </SecondaryButton>
        )}
        {status === "paused" && (
          <SecondaryButton type="button" disabled={loading} onClick={() => updateStatus("active")}>
            Resume
          </SecondaryButton>
        )}
        {status !== "closed" && status !== "archived" && (
          <SecondaryButton type="button" disabled={loading} onClick={() => updateStatus("closed")}>
            Close
          </SecondaryButton>
        )}
        <SecondaryButton type="button" disabled={duplicating} onClick={duplicate}>
          Duplicate
        </SecondaryButton>
      </div>
    </article>
  );
}
