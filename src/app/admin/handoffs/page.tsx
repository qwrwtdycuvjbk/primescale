import { Suspense } from "react";
import { HandoffCard } from "@/components/admin/HandoffCard";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { AdminHandoffFilters } from "@/components/admin/AdminHandoffFilters";
import { requireAdmin } from "@/lib/auth";
import { getAdminClient } from "@/lib/supabase/admin";
import type { HandoffRequest, HandoffStatus, Profile } from "@/lib/types";

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
  const supabase = await getAdminClient();

  let query = supabase
    .from("handoff_requests")
    .select(
      `
      id,
      match_id,
      status,
      notes,
      created_at,
      updated_at,
      matches (
        id,
        candidate_profile_id,
        job_id,
        match_score,
        match_reason,
        status,
        created_at,
        updated_at,
        jobs (
          title,
          salary_range,
          posted_by,
          companies ( name )
        ),
        candidate_profiles (
          id,
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
    .order("created_at", { ascending: false })
    .limit(50);

  if (status && status !== "all" && handoffStatuses.includes(status as HandoffStatus)) {
    query = query.eq("status", status);
  }

  const { data: rawHandoffs } = await query;

  const employerIds = [
    ...new Set(
      (rawHandoffs ?? [])
        .map((handoff) => {
          const matchRaw = handoff.matches;
          const match = Array.isArray(matchRaw) ? matchRaw[0] : matchRaw;
          const jobs = match?.jobs as { posted_by?: string } | { posted_by?: string }[] | undefined;
          const job = Array.isArray(jobs) ? jobs[0] : jobs;
          return job?.posted_by;
        })
        .filter((id): id is string => Boolean(id)),
    ),
  ];

  const [{ data: employers }, { count: pendingCount }] = await Promise.all([
    employerIds.length
      ? supabase
          .from("profiles")
          .select("id, full_name, email, phone")
          .in("id", employerIds)
      : Promise.resolve({
          data: [] as Pick<Profile, "id" | "full_name" | "email" | "phone">[],
        }),
    supabase
      .from("handoff_requests")
      .select("id", { count: "exact", head: true })
      .eq("status", "pending"),
  ]);

  const employerById = new Map((employers ?? []).map((row) => [row.id, row]));

  const handoffs = (rawHandoffs ?? []).map((handoff) => {
    const matchRaw = handoff.matches;
    const match = Array.isArray(matchRaw) ? matchRaw[0] : matchRaw;
    const jobsRaw = match?.jobs;
    const job = Array.isArray(jobsRaw) ? jobsRaw[0] : jobsRaw;
    const employer = job?.posted_by
      ? employerById.get(job.posted_by)
      : undefined;

    return {
      ...handoff,
      matches: match
        ? {
            ...match,
            jobs: job
              ? {
                  ...job,
                  companies: Array.isArray(job.companies)
                    ? job.companies[0]
                    : job.companies,
                }
              : undefined,
            candidate_profiles: (() => {
              const candidateRaw = match.candidate_profiles;
              const candidate = Array.isArray(candidateRaw)
                ? candidateRaw[0]
                : candidateRaw;
              if (!candidate) return undefined;
              const profileRaw = candidate.profiles;
              return {
                ...candidate,
                profiles: Array.isArray(profileRaw) ? profileRaw[0] : profileRaw,
              };
            })(),
          }
        : undefined,
      employer,
    } as unknown as HandoffRequest & {
      employer?: Pick<Profile, "full_name" | "email" | "phone">;
    };
  });

  return (
    <AdminShell name={profile.full_name} activePath="/admin/handoffs">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          People Prime <span className="italic text-foreground">handoffs.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Mutual-fit matches from People Remotely. Contact both parties, coordinate
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
