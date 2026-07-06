import { Suspense } from "react";
import { HandoffCard } from "@/components/admin/HandoffCard";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminHandoffFilters } from "@/components/admin/AdminHandoffFilters";
import { requireAdmin } from "@/lib/auth";
import { getServiceClient } from "@/lib/supabase/service";
import type { HandoffRequest, HandoffStatus, Profile } from "@/lib/types";
import { redirect } from "next/navigation";

const handoffStatuses: HandoffStatus[] = [
  "pending",
  "contacted",
  "intro_made",
  "closed",
];

export default async function AdminHandoffsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const { profile } = await requireAdmin();
  const supabase = getServiceClient();
  if (!supabase) redirect("/");

  let query = supabase
    .from("handoff_requests")
    .select(
      `
      *,
      matches (
        id,
        match_score,
        match_reason,
        status,
        jobs (
          title,
          salary_range,
          posted_by,
          companies ( name )
        ),
        candidate_profiles (
          headline,
          skills,
          linkedin_url,
          github_url,
          resume_url,
          profiles ( full_name, email, phone )
        )
      )
    `,
    )
    .order("created_at", { ascending: false });

  if (status && status !== "all" && handoffStatuses.includes(status as HandoffStatus)) {
    query = query.eq("status", status);
  }

  const { data: rawHandoffs } = await query;

  const employerIds = [
    ...new Set(
      (rawHandoffs ?? [])
        .map((handoff) => {
          const jobs = handoff.matches?.jobs as { posted_by?: string } | undefined;
          return jobs?.posted_by;
        })
        .filter((id): id is string => Boolean(id)),
    ),
  ];

  const { data: employers } = employerIds.length
    ? await supabase
        .from("profiles")
        .select("id, full_name, email, phone")
        .in("id", employerIds)
    : { data: [] as Pick<Profile, "id" | "full_name" | "email" | "phone">[] };

  const employerById = new Map((employers ?? []).map((row) => [row.id, row]));

  const handoffs = (rawHandoffs ?? []).map((handoff) => {
    const jobs = handoff.matches?.jobs as { posted_by?: string } | undefined;
    const employer = jobs?.posted_by
      ? employerById.get(jobs.posted_by)
      : undefined;

    return {
      ...handoff,
      employer,
    } as HandoffRequest & { employer?: Pick<Profile, "full_name" | "email" | "phone"> };
  });

  const { count: pendingCount } = await supabase
    .from("handoff_requests")
    .select("*", { count: "exact", head: true })
    .eq("status", "pending");

  return (
    <AdminShell name={profile.full_name} activePath="/admin/handoffs">
      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <h1 className="display-headline text-4xl sm:text-5xl">
          People Prime <span className="italic text-primary">handoffs.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Mutual-fit matches from PrimeScale. Contact both parties, coordinate
          intros, and update queue status here.
        </p>

        <div className="mt-8 rounded-2xl border border-border bg-card px-5 py-4">
          <p className="text-2xl font-semibold">{pendingCount ?? 0}</p>
          <p className="mt-1 text-sm text-muted-foreground">Pending handoffs</p>
        </div>

        <div className="mt-8">
          <Suspense fallback={<div className="h-12" />}>
            <AdminHandoffFilters />
          </Suspense>
        </div>

        <div className="mt-8 space-y-4">
          {handoffs.length ? (
            handoffs.map((handoff) => (
              <HandoffCard key={handoff.id} handoff={handoff} />
            ))
          ) : (
            <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
              <p className="text-lg font-medium">No handoffs in this view</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Handoffs appear when an employer shortlists a candidate who already
                marked interest, or vice versa.
              </p>
            </div>
          )}
        </div>
      </main>
    </AdminShell>
  );
}
