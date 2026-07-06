"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Match } from "@/lib/types";
import { PrimaryButton, SecondaryButton } from "@/components/site/form";

export function RecruiterMatchReviewCard({ match }: { match: Match }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const candidate = match.candidate_profiles;
  const job = match.jobs;
  const name = candidate?.profiles?.full_name ?? "Candidate";

  async function review(action: "approve" | "reject") {
    setLoading(true);
    setMessage("");
    try {
      const response = await fetch(`/api/admin/matches/${match.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!response.ok) {
        setMessage("Could not update match.");
        return;
      }
      setMessage(action === "approve" ? "Sent to employer." : "Rejected.");
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
            {match.match_score}% match
          </p>
          <h3 className="display-headline mt-2 text-2xl">
            {name} → {job?.title ?? "Role"}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {job?.companies?.name ?? "Company"}
          </p>
          {candidate?.headline && (
            <p className="mt-2 text-sm text-muted-foreground">{candidate.headline}</p>
          )}
        </div>
        <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-700">
          Awaiting review
        </span>
      </div>

      {match.match_reason && (
        <p className="mt-4 text-sm text-muted-foreground">{match.match_reason}</p>
      )}

      {candidate?.skills && (
        <div className="mt-4 flex flex-wrap gap-2">
          {candidate.skills.slice(0, 10).map((skill) => (
            <span key={skill} className="rounded-full border border-border px-3 py-1 text-xs">
              {skill}
            </span>
          ))}
        </div>
      )}

      <div className="mt-6 flex flex-wrap gap-3">
        <PrimaryButton type="button" disabled={loading} onClick={() => review("approve")}>
          Approve for employer
        </PrimaryButton>
        <SecondaryButton type="button" disabled={loading} onClick={() => review("reject")}>
          Reject
        </SecondaryButton>
      </div>

      {message && <p className="mt-3 text-sm text-muted-foreground">{message}</p>}
    </article>
  );
}
