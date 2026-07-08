"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Job, Match, MatchStatus } from "@/lib/types";
import { workAuthLabel } from "@/lib/constants";
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
      if (response.ok) {
        const data = (await response.json()) as { status?: MatchStatus };
        setStatus(data.status ?? newStatus);
      }
    } finally {
      setLoading(false);
    }
  }

  const candidate = match.candidate_profiles;
  const name = candidate?.profiles?.full_name ?? "Candidate";
  const jobTitle = match.jobs?.title;

  const meta = [
    candidate?.current_title,
    candidate?.experience_level
      ? `${candidate.experience_level} level`
      : null,
    candidate?.years_experience != null
      ? `${candidate.years_experience} yrs exp`
      : null,
    candidate?.work_authorization
      ? workAuthLabel(candidate.work_authorization)
      : null,
    candidate?.us_state,
    candidate?.remote_preference,
  ].filter(Boolean);

  return (
    <article className="rounded-3xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          {jobTitle && (
            <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
              For {jobTitle}
            </p>
          )}
          <p className="font-mono text-xs uppercase tracking-widest text-primary">
            {match.match_score}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">{name}</h3>
          {candidate?.headline && (
            <p className="mt-1 text-sm text-muted-foreground">{candidate.headline}</p>
          )}
          {meta.length > 0 && (
            <p className="mt-2 text-sm text-muted-foreground">{meta.join(" · ")}</p>
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
      {(candidate?.linkedin_url || candidate?.github_url) && (
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          {candidate.linkedin_url && (
            <a
              href={candidate.linkedin_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              LinkedIn
            </a>
          )}
          {candidate.github_url && (
            <a
              href={candidate.github_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              GitHub
            </a>
          )}
        </div>
      )}
      {status === "mutual_fit" && (
        <p className="mt-6 rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-foreground">
          Mutual fit confirmed. People Prime is coordinating an intro with this
          candidate.
        </p>
      )}
      {status !== "rejected" &&
        status !== "employer_shortlisted" &&
        status !== "mutual_fit" && (
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
              Expires{" "}
              {new Date(job.expires_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
                timeZone: "UTC",
              })}
            </p>
          )}
        </div>
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
