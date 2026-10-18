"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight } from "lucide-react";
import type { Match, MatchStatus } from "@/lib/types";
import { PrimaryButton, SecondaryButton } from "@/components/site/form";

export function CandidateMatchCard({ match }: { match: Match }) {
  const [status, setStatus] = useState(match.status);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function updateStatus(newStatus: MatchStatus) {
    setErrorMsg(null);
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
      } else {
        const errData = await response.json().catch(() => ({}));
        setErrorMsg(
          errData?.error || "Please complete your profile before applying for jobs."
        );
      }
    } catch {
      setErrorMsg("Please complete your profile before applying for jobs.");
    } finally {
      setLoading(false);
    }
  }

  const job = match.jobs || (match as any).job;
  const companyName = job?.companies?.name || job?.company_name || (job as any)?.company?.name;
  const jobMeta = [
    job?.experience_level ? `${job.experience_level} level` : null,
    job?.role_type,
    job?.work_type,
    job?.salary_range,
  ].filter(Boolean);

  return (
    <article className="rounded-3xl border border-border bg-card p-6 transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-foreground">
            {match.match_score}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">
            {job?.title ?? "Role"}
          </h3>
          {companyName && (
            <p className="mt-1 text-sm font-medium text-muted-foreground">
              {companyName}
            </p>
          )}
          {jobMeta.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground/80">
              {jobMeta.join(" · ")}
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
          {job.tech_stack.slice(0, 6).map((skill: string) => (
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

      {errorMsg && (
        <div className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 text-xs font-semibold">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <Link
            href="/candidate/onboarding"
            className="shrink-0 rounded-full bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-90 transition-opacity"
          >
            Complete Profile
          </Link>
        </div>
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
        We scan active tech roles against your profile. Make sure your skills
        and resume are up to date for better matching.
      </p>
      <Link href={editProfileHref} className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-foreground hover:text-foreground">
        Update profile
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
