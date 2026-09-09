import { Suspense } from "react";
import { AdminCandidateActions } from "@/components/admin/AdminCandidateActions";
import { AdminCandidateFilters } from "@/components/admin/AdminCandidateFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import {
  CandidateRegistryTable,
  type AdminCandidateRow,
} from "@/components/admin/CandidateRegistryTable";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { candidatesApi } from "@/lib/api";

const PAGE_SIZE = 100;

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
  const token = await getAccessToken();

  let candidates: AdminCandidateRow[] = [];
  let totalCount = 0;
  let completeCount = 0;
  let activeCount = 0;

  try {
    const djangoRes = await candidatesApi.listAdminCandidates(
      {
        q: filters.q,
        complete: filters.complete,
        availability: filters.availability,
        experience: filters.experience,
        work_auth: filters.work_auth,
        matching: filters.matching,
        resume: filters.resume,
        source: filters.source,
        limit: PAGE_SIZE,
      },
      { token },
    );
    if (djangoRes && Array.isArray(djangoRes.candidates)) {
      candidates = djangoRes.candidates as AdminCandidateRow[];
      totalCount = djangoRes.totalCount ?? djangoRes.count;
      completeCount = djangoRes.completeCount ?? 0;
      activeCount = djangoRes.activeCount ?? 0;
    }
  } catch (err) {
    console.error("Failed to load candidates from Django:", err);
  }

  return (
    <AdminShell name={profile.full_name} activePath="/admin/candidates">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Candidate <span className="italic text-foreground">registry.</span>
            </h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Everyone who signed up as a candidate on People Remotely. Filter by profile
              status, experience, work authorization, availability, and more.
            </p>
          </div>
          <AdminCandidateActions />
        </div>

        {filters.added === "1" && (
          <div className="mt-8 rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4">
            <p className="font-medium text-foreground">Candidate added successfully.</p>
            {filters.matches && Number(filters.matches) > 0 && (
              <p className="mt-1 text-sm text-muted-foreground">
                {filters.matches} automatic match
                {Number(filters.matches) === 1 ? "" : "es"} created.
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
          {candidates.length >= PAGE_SIZE ? ` (latest ${PAGE_SIZE})` : ""}
        </p>

        <div className="mt-4">
          <CandidateRegistryTable candidates={candidates} />
        </div>
      </main>
    </AdminShell>
  );
}
