"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle } from "lucide-react";
import type { Match, MatchStatus } from "@/lib/types";
import { buttonPrimaryClass, buttonSecondaryClass } from "@/lib/ui";

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
        setStatus(newStatus);
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

  const job = match.jobs;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-teal-600">
            {match.match_score}% match
          </p>
          <h3 className="mt-1 text-xl font-semibold text-slate-900">
            {job?.title ?? "Role"}
          </h3>
          {job?.companies?.name && (
            <p className="mt-1 text-sm text-slate-500">{job.companies.name}</p>
          )}
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {status.replace(/_/g, " ")}
        </span>
      </div>

      {match.match_reason && (
        <p className="mt-4 text-sm leading-relaxed text-slate-600">
          {match.match_reason}
        </p>
      )}

      {job && (
        <div className="mt-4 flex flex-wrap gap-2">
          {job.tech_stack?.slice(0, 6).map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {errorMsg && (
        <div className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 text-xs font-semibold">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <Link
            href="/candidate/onboarding"
            className="shrink-0 rounded-full bg-teal-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 transition-colors"
          >
            Complete Profile
          </Link>
        </div>
      )}

      {status === "suggested" && (
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={loading}
            onClick={() => updateStatus("candidate_interested")}
            className={buttonPrimaryClass}
          >
            I&apos;m interested
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => updateStatus("rejected")}
            className={buttonSecondaryClass}
          >
            Not for me
          </button>
        </div>
      )}
    </article>
  );
}

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
    <article className="rounded-2xl border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-teal-600">
            {match.match_score}% match
          </p>
          <h3 className="mt-1 text-xl font-semibold text-slate-900">{name}</h3>
          {candidate?.headline && (
            <p className="mt-1 text-sm text-slate-500">{candidate.headline}</p>
          )}
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
          {status.replace(/_/g, " ")}
        </span>
      </div>

      {match.match_reason && (
        <p className="mt-4 text-sm leading-relaxed text-slate-600">
          {match.match_reason}
        </p>
      )}

      {candidate?.skills && (
        <div className="mt-4 flex flex-wrap gap-2">
          {candidate.skills.slice(0, 8).map((skill) => (
            <span
              key={skill}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {status !== "rejected" && status !== "employer_shortlisted" && (
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            disabled={loading}
            onClick={() => updateStatus("employer_shortlisted")}
            className={buttonPrimaryClass}
          >
            Shortlist
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => updateStatus("rejected")}
            className={buttonSecondaryClass}
          >
            Pass
          </button>
        </div>
      )}
    </article>
  );
}
