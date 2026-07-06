"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { HandoffRequest, HandoffStatus, Profile } from "@/lib/types";
import { PrimaryButton, fieldInputClass } from "@/components/site/form";

type HandoffWithEmployer = HandoffRequest & {
  employer?: Pick<Profile, "full_name" | "email" | "phone">;
};

const statusOptions: { value: HandoffStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "contacted", label: "Contacted" },
  { value: "intro_made", label: "Intro made" },
  { value: "closed", label: "Closed" },
];

export function HandoffCard({ handoff }: { handoff: HandoffWithEmployer }) {
  const router = useRouter();
  const [status, setStatus] = useState(handoff.status);
  const [notes, setNotes] = useState(handoff.notes ?? "");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const match = handoff.matches;
  const job = match?.jobs;
  const companyName = job?.companies?.name ?? "Company";
  const candidate = match?.candidate_profiles;
  const candidateProfile = candidate?.profiles;

  async function save() {
    setLoading(true);
    setMessage("");
    try {
      const response = await fetch(`/api/admin/handoffs/${handoff.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, notes }),
      });
      if (!response.ok) {
        setMessage("Could not save changes.");
        return;
      }
      setMessage("Saved.");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <article className="rounded-3xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-primary">
            {match?.match_score ?? 0}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">
            {candidateProfile?.full_name ?? "Candidate"} → {job?.title ?? "Role"}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">{companyName}</p>
        </div>
        <span className="rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize">
          {status.replace(/_/g, " ")}
        </span>
      </div>

      {match?.match_reason && (
        <p className="mt-4 text-sm text-muted-foreground">{match.match_reason}</p>
      )}

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Employer
          </p>
          <p className="mt-2 font-medium">{handoff.employer?.full_name ?? "—"}</p>
          <p className="mt-1 text-sm text-muted-foreground">{handoff.employer?.email ?? "—"}</p>
          {handoff.employer?.phone && (
            <p className="mt-1 text-sm text-muted-foreground">{handoff.employer.phone}</p>
          )}
        </div>
        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Candidate
          </p>
          <p className="mt-2 font-medium">{candidateProfile?.full_name ?? "—"}</p>
          <p className="mt-1 text-sm text-muted-foreground">{candidateProfile?.email ?? "—"}</p>
          {candidate?.headline && (
            <p className="mt-2 text-sm text-muted-foreground">{candidate.headline}</p>
          )}
          <div className="mt-3 flex flex-wrap gap-3 text-sm">
            {candidate?.linkedin_url && (
              <a href={candidate.linkedin_url} target="_blank" rel="noreferrer" className="underline">
                LinkedIn
              </a>
            )}
            {candidate?.github_url && (
              <a href={candidate.github_url} target="_blank" rel="noreferrer" className="underline">
                GitHub
              </a>
            )}
            {candidate?.resume_url && (
              <a href={candidate.resume_url} target="_blank" rel="noreferrer" className="underline">
                Resume
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-[180px_1fr]">
        <div>
          <label htmlFor={`status-${handoff.id}`} className="text-sm font-medium">
            Queue status
          </label>
          <select
            id={`status-${handoff.id}`}
            value={status}
            onChange={(event) => setStatus(event.target.value as HandoffStatus)}
            className={`${fieldInputClass} mt-2`}
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`notes-${handoff.id}`} className="text-sm font-medium">
            Recruiter notes
          </label>
          <textarea
            id={`notes-${handoff.id}`}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={3}
            className={`${fieldInputClass} mt-2 resize-y`}
            placeholder="Call notes, intro status, next steps..."
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <PrimaryButton type="button" disabled={loading} onClick={save}>
          Save
        </PrimaryButton>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Created {new Date(handoff.created_at).toLocaleString()}
        {handoff.notified_at
          ? ` · Email sent ${new Date(handoff.notified_at).toLocaleString()}`
          : " · Email not sent (check RESEND_API_KEY)"}
      </p>
    </article>
  );
}
