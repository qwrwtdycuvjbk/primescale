import { Suspense } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AdminJobFilters } from "@/components/admin/AdminJobFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import {
  JobRegistryTable,
  type AdminJobRow,
} from "@/components/admin/JobRegistryTable";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";
import { getAdminClient } from "@/lib/supabase/admin";
import type { Company, Job, Profile } from "@/lib/types";

const PAGE_SIZE = 100;

type RawJobRow = Pick<
  Job,
  | "id"
  | "company_id"
  | "posted_by"
  | "title"
  | "role_type"
  | "experience_level"
  | "tech_stack"
  | "salary_range"
  | "work_type"
  | "status"
  | "expires_at"
  | "created_at"
  | "updated_at"
> & {
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
  const supabase = await getAdminClient();

  let query = supabase
    .from("jobs")
    .select(
      `
      id,
      company_id,
      posted_by,
      title,
      role_type,
      experience_level,
      tech_stack,
      salary_range,
      work_type,
      status,
      expires_at,
      created_at,
      updated_at,
      companies ( name, website ),
      profiles:posted_by ( full_name, email, phone )
    `,
    )
    .order("created_at", { ascending: false })
    .limit(PAGE_SIZE);

  if (filters.status && filters.status !== "all") {
    query = query.eq("status", filters.status);
  }

  if (filters.experience && filters.experience !== "all") {
    query = query.eq("experience_level", filters.experience);
  }

  if (filters.role_type && filters.role_type !== "all") {
    query = query.eq("role_type", filters.role_type);
  }

  if (filters.q?.trim()) {
    query = query.ilike("title", `%${filters.q.trim()}%`);
  }

  const [
    { data: rawJobs },
    { count: totalCount },
    { count: activeCount },
    { count: draftCount },
  ] = await Promise.all([
    query,
    supabase.from("jobs").select("id", { count: "exact", head: true }),
    supabase
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .eq("status", "active"),
    supabase
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .eq("status", "draft"),
  ]);

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

  // Company / poster search on the already-fetched page (title is DB-filtered above).
  if (filters.q?.trim()) {
    const term = filters.q.trim().toLowerCase();
    const titleOnly = jobs.filter((job) => job.title.toLowerCase().includes(term));
    if (titleOnly.length === 0) {
      jobs = jobs.filter((job) => {
        const company = job.companies?.name?.toLowerCase() ?? "";
        const email = job.profiles?.email?.toLowerCase() ?? "";
        return company.includes(term) || email.includes(term);
      });
    }
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
      matchCountByJob.set(row.job_id, (matchCountByJob.get(row.job_id) ?? 0) + 1);

      if (row.visible_to_employer) {
        releasedCountByJob.set(
          row.job_id,
          (releasedCountByJob.get(row.job_id) ?? 0) + 1,
        );
      }
    }
  }

  jobs = jobs.map((job) => ({
    ...job,
    matchCount: matchCountByJob.get(job.id) ?? 0,
    releasedMatchCount: releasedCountByJob.get(job.id) ?? 0,
  }));

  return (
    <AdminShell name={profile.full_name} activePath="/admin/jobs">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Posted <span className="italic text-foreground">roles.</span>
            </h1>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Every job companies have posted on People Remotely. Filter by status,
              experience level, and role type.
            </p>
          </div>
          <Link
            href="/admin/jobs/new"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Add job
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

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
          {jobs.length >= PAGE_SIZE ? ` (latest ${PAGE_SIZE})` : ""}
        </p>

        <div className="mt-4">
          <JobRegistryTable jobs={jobs} />
        </div>
      </main>
    </AdminShell>
  );
}
