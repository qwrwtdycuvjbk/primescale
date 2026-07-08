import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AdminCandidateFilters } from "@/components/admin/AdminCandidateFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import {
  CandidateRegistryTable,
  type AdminCandidateRow,
} from "@/components/admin/CandidateRegistryTable";
import { requireAdmin } from "@/lib/auth";
import { getServiceClient } from "@/lib/supabase/service";
import type { MatchStatus } from "@/lib/types";
import { redirect } from "next/navigation";

const roleApplicationStatuses: MatchStatus[] = [
  "candidate_interested",
  "employer_shortlisted",
  "mutual_fit",
];

export default async function AdminCandidatesPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    complete?: string;
    availability?: string;
    experience?: string;
    work_auth?: string;
    matching?: string;
    resume?: string;
    source?: string;
    added?: string;
    matches?: string;
  }>;
}) {
  const filters = await searchParams;
  const { profile } = await requireAdmin();
  const supabase = getServiceClient();
  if (!supabase) redirect("/");

  let query = supabase
    .from("candidate_profiles")
    .select(
      `
      *,
      profiles!inner ( full_name, email, phone, created_at, role )
    `,
    )
    .eq("profiles.role", "candidate")
    .order("created_at", { ascending: false });

  if (filters.complete === "yes") query = query.eq("profile_complete", true);
  if (filters.complete === "no") query = query.eq("profile_complete", false);

  if (filters.availability && filters.availability !== "all") {
    query = query.eq("availability_status", filters.availability);
  }

  if (filters.experience && filters.experience !== "all") {
    query = query.eq("experience_level", filters.experience);
  }

  if (filters.work_auth && filters.work_auth !== "all") {
    query = query.eq("work_authorization", filters.work_auth);
  }

  if (filters.matching === "yes") query = query.eq("open_to_matching", true);
  if (filters.matching === "no") query = query.eq("open_to_matching", false);

  if (filters.resume === "yes") query = query.not("resume_url", "is", null);
  if (filters.resume === "no") query = query.is("resume_url", null);

  if (filters.source && filters.source !== "all") {
    query = query.eq("source", filters.source);
  }

  const { data: rawCandidates } = await query;

  let candidates = (rawCandidates ?? []) as AdminCandidateRow[];

  if (filters.q?.trim()) {
    const term = filters.q.trim().toLowerCase();
    candidates = candidates.filter((candidate) => {
      const name = candidate.profiles.full_name?.toLowerCase() ?? "";
      const email = candidate.profiles.email?.toLowerCase() ?? "";
      return name.includes(term) || email.includes(term);
    });
  }

  const candidateIds = candidates.map((candidate) => candidate.id);
  const applicationCountByCandidate = new Map<string, number>();

  if (candidateIds.length) {
    const { data: applications } = await supabase
      .from("matches")
      .select("candidate_profile_id")
      .in("candidate_profile_id", candidateIds)
      .in("status", roleApplicationStatuses);

    for (const row of applications ?? []) {
      const current = applicationCountByCandidate.get(row.candidate_profile_id) ?? 0;
      applicationCountByCandidate.set(row.candidate_profile_id, current + 1);
    }
  }

  candidates = candidates.map((candidate) => ({
    ...candidate,
    roleApplications: applicationCountByCandidate.get(candidate.id) ?? 0,
  }));

  const { count: totalCount } = await supabase
    .from("candidate_profiles")
    .select("*, profiles!inner(role)", { count: "exact", head: true })
    .eq("profiles.role", "candidate");

  const { count: completeCount } = await supabase
    .from("candidate_profiles")
    .select("*, profiles!inner(role)", { count: "exact", head: true })
    .eq("profiles.role", "candidate")
    .eq("profile_complete", true);

  const { count: activeCount } = await supabase
    .from("candidate_profiles")
    .select("*, profiles!inner(role)", { count: "exact", head: true })
    .eq("profiles.role", "candidate")
    .eq("availability_status", "actively_looking");

  return (
    <AdminShell name={profile.full_name} activePath="/admin/candidates">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Candidate <span className="italic text-primary">registry.</span>
            </h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Everyone who signed up as a candidate on PrimeScale. Filter by profile
              status, experience, work authorization, availability, and more.
            </p>
          </div>
          <Link
            href="/admin/candidates/new"
            className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Add candidate
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {filters.added === "1" && (
          <div className="mt-8 rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4">
            <p className="font-medium text-primary">Candidate added successfully.</p>
            {filters.matches && Number(filters.matches) > 0 && (
              <p className="mt-1 text-sm text-muted-foreground">
                {filters.matches} automatic match{Number(filters.matches) === 1 ? "" : "es"} created.
              </p>
            )}
          </div>
        )}

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{totalCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Total candidates</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{completeCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Complete profiles</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{activeCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Actively looking</p>
          </div>
        </div>

        <div className="mt-8">
          <Suspense fallback={<div className="h-40" />}>
            <AdminCandidateFilters />
          </Suspense>
        </div>

        <p className="mt-6 text-sm text-muted-foreground">
          Showing {candidates.length} candidate{candidates.length === 1 ? "" : "s"}
        </p>

        <div className="mt-4">
          <CandidateRegistryTable candidates={candidates} />
        </div>
      </main>
    </AdminShell>
  );
}
