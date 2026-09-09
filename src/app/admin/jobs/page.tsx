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
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { jobsApi } from "@/lib/api";

const PAGE_SIZE = 100;

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
  const token = await getAccessToken();

  let jobs: AdminJobRow[] = [];
  let totalCount = 0;
  let activeCount = 0;
  let draftCount = 0;

  try {
    const djangoJobs = await jobsApi.listJobs(
      {
        q: filters.q,
        status: filters.status,
        experience_level: filters.experience,
        role_type: filters.role_type,
      },
      { token },
    );

    if (Array.isArray(djangoJobs)) {
      totalCount = djangoJobs.length;
      activeCount = djangoJobs.filter((j) => j.status === "active").length;
      draftCount = djangoJobs.filter((j) => j.status === "draft").length;

      jobs = djangoJobs.slice(0, PAGE_SIZE).map((j: any) => ({
        id: j.id,
        company_id: j.company_id || j.company || "",
        posted_by: j.posted_by || "",
        title: j.title,
        role_type: j.role_type,
        experience_level: j.experience_level,
        tech_stack: j.tech_stack || [],
        salary_range: j.salary_range || "",
        work_type: j.work_type || "remote",
        status: j.status,
        expires_at: j.expires_at || null,
        created_at: j.created_at || "",
        updated_at: j.updated_at || "",
        companies: j.companies || j.company_details || (j.company ? { name: j.company } : null),
        profiles: {
          full_name: j.posted_by_full_name || "",
          email: j.posted_by_email || "",
          phone: undefined,
        },
        matchCount: 0,
        releasedMatchCount: 0,
      }));
    }
  } catch (err) {
    console.error("Failed to load jobs from Django:", err);
  }

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
