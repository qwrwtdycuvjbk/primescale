import { Suspense } from "react";
import { AdminJobFilters } from "@/components/admin/AdminJobFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import {
  JobRegistryTable,
  type AdminJobRow,
} from "@/components/admin/JobRegistryTable";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";
import { getServiceClient } from "@/lib/supabase/service";
import type { Company, Job, Profile } from "@/lib/types";
import { redirect } from "next/navigation";

type RawJobRow = Job & {
  companies: Pick<Company, "name" | "website"> | Pick<Company, "name" | "website">[] | null;
  profiles: Pick<Profile, "full_name" | "email" | "phone"> | Pick<Profile, "full_name" | "email" | "phone">[] | null;
};

function unwrapRelation<T>(value: T | T[] | null | undefined): T | null {
  if (!value) return null;
  return Array.isArray(value) ? (value[0] ?? null) : value;
}

export default async function AdminJobsPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    status?: string;
    experience?: string;
    role_type?: string;
  }>;
}) {
  const filters = await searchParams;
  const { profile } = await requireAdmin();
  const supabase = getServiceClient();
  if (!supabase) redirect("/");

  let query = supabase
    .from("jobs")
    .select(
      `
      *,
      companies ( name, website ),
      profiles:posted_by ( full_name, email, phone )
    `,
    )
    .order("created_at", { ascending: false });

  if (filters.status && filters.status !== "all") {
    query = query.eq("status", filters.status);
  }

  if (filters.experience && filters.experience !== "all") {
    query = query.eq("experience_level", filters.experience);
  }

  if (filters.role_type && filters.role_type !== "all") {
    query = query.eq("role_type", filters.role_type);
  }

  const { data: rawJobs } = await query;

  let jobs: AdminJobRow[] = (rawJobs ?? []).map((row) => {
    const job = row as RawJobRow;
    return {
      ...job,
      companies: unwrapRelation(job.companies),
      profiles: unwrapRelation(job.profiles),
      matchCount: 0,
      releasedMatchCount: 0,
    };
  });

  if (filters.q?.trim()) {
    const term = filters.q.trim().toLowerCase();
    jobs = jobs.filter((job) => {
      const title = job.title.toLowerCase();
      const company = job.companies?.name?.toLowerCase() ?? "";
      const email = job.profiles?.email?.toLowerCase() ?? "";
      return title.includes(term) || company.includes(term) || email.includes(term);
    });
  }

  const jobIds = jobs.map((job) => job.id);
  const matchCountByJob = new Map<string, number>();
  const releasedCountByJob = new Map<string, number>();

  if (jobIds.length) {
    const { data: matches } = await supabase
      .from("matches")
      .select("job_id, visible_to_employer")
      .in("job_id", jobIds);

    for (const row of matches ?? []) {
      const current = matchCountByJob.get(row.job_id) ?? 0;
      matchCountByJob.set(row.job_id, current + 1);

      if (row.visible_to_employer) {
        const released = releasedCountByJob.get(row.job_id) ?? 0;
        releasedCountByJob.set(row.job_id, released + 1);
      }
    }
  }

  jobs = jobs.map((job) => ({
    ...job,
    matchCount: matchCountByJob.get(job.id) ?? 0,
    releasedMatchCount: releasedCountByJob.get(job.id) ?? 0,
  }));

  const { count: totalCount } = await supabase
    .from("jobs")
    .select("*", { count: "exact", head: true });

  const { count: activeCount } = await supabase
    .from("jobs")
    .select("*", { count: "exact", head: true })
    .eq("status", "active");

  const { count: draftCount } = await supabase
    .from("jobs")
    .select("*", { count: "exact", head: true })
    .eq("status", "draft");

  return (
    <AdminShell name={profile.full_name} activePath="/admin/jobs">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Posted <span className="italic text-primary">roles.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Every job companies have posted on PrimeScale. Filter by status,
          experience level, and role type.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{totalCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Total roles</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{activeCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Active</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{draftCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Drafts</p>
          </div>
        </div>

        <div className="mt-8">
          <Suspense fallback={<div className="h-40" />}>
            <AdminJobFilters />
          </Suspense>
        </div>

        <p className="mt-6 text-sm text-muted-foreground">
          Showing {jobs.length} role{jobs.length === 1 ? "" : "s"}
        </p>

        <div className="mt-4">
          <JobRegistryTable jobs={jobs} />
        </div>
      </main>
    </AdminShell>
  );
}
