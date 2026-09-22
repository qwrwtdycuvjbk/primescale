import Link from "next/link";
import {
  Briefcase,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileText,
  Filter,
  Search,
  User,
  XCircle,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { applicationsApi, jobsApi } from "@/lib/api";
import type { DjangoApplication } from "@/lib/api/applications";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function applicationStatusBadge(status: string) {
  switch (status) {
    case "candidate_interested":
      return {
        label: "Candidate Applied",
        bg: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
      };
    case "employer_shortlisted":
      return {
        label: "Shortlisted",
        bg: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
      };
    case "mutual_fit":
      return {
        label: "Mutual Fit",
        bg: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
      };
    case "rejected":
      return {
        label: "Rejected",
        bg: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
      };
    case "suggested":
    case "admin_approved":
      return {
        label: "Recruiter Matched",
        bg: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
      };
    default:
      return {
        label: status.replace("_", " "),
        bg: "bg-muted text-muted-foreground border-border",
      };
  }
}

export default async function AdminApplicationsPage({
  searchParams,
}: {
  searchParams: Promise<{
    status?: string;
    job_id?: string;
    q?: string;
  }>;
}) {
  const filters = await searchParams;
  const { profile } = await requireAdmin();
  const token = await getAccessToken();

  let applications: DjangoApplication[] = [];
  let totalCount = 0;
  let appliedCount = 0;
  let shortlistedCount = 0;
  let mutualCount = 0;
  let errorMsg: string | null = null;

  try {
    const rawApps = await applicationsApi.listApplications(
      {
        status: filters.status && filters.status !== "all" ? filters.status : undefined,
        job_id: filters.job_id && filters.job_id !== "all" ? filters.job_id : undefined,
      },
      { token },
    );

    if (rawApps && Array.isArray(rawApps)) {
      let filtered = rawApps;
      if (filters.q) {
        const query = filters.q.toLowerCase().trim();
        filtered = filtered.filter((app) => {
          const candName = (
            app.candidate_profile?.user?.full_name ||
            app.candidate_profile?.full_name ||
            app.candidate_profiles?.full_name ||
            ""
          ).toLowerCase();
          const candEmail = (
            app.candidate_profile?.user?.email ||
            app.candidate_profile?.email ||
            app.candidate_profiles?.email ||
            ""
          ).toLowerCase();
          const jobTitle = (
            app.job?.title ||
            app.jobs?.title ||
            app.job_title ||
            ""
          ).toLowerCase();
          const company = (
            (app.job as any)?.company?.name ||
            app.job?.companies?.name ||
            app.job?.company_name ||
            ""
          ).toLowerCase();

          return (
            candName.includes(query) ||
            candEmail.includes(query) ||
            jobTitle.includes(query) ||
            company.includes(query)
          );
        });
      }

      applications = filtered;
      totalCount = rawApps.length;
      appliedCount = rawApps.filter((a) => a.status === "candidate_interested").length;
      shortlistedCount = rawApps.filter((a) => a.status === "employer_shortlisted").length;
      mutualCount = rawApps.filter((a) => a.status === "mutual_fit").length;
    }
  } catch (err: any) {
    console.error("Failed to load applications:", err);
    errorMsg = err?.message || "Failed to load applications from Django backend.";
  }

  return (
    <AdminShell name={profile.full_name} activePath="/admin/applications">
      <main className={appMainClass}>
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Job <span className="italic text-foreground">applications.</span>
            </h1>
            <p className="mt-2 text-muted-foreground max-w-2xl">
              Track candidates applying to live jobs, employer shortlist actions, and mutual fit progression.
            </p>
          </div>
        </div>

        {/* Metric KPI Cards */}
        <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-3xl font-bold">{totalCount}</p>
            <p className="mt-1 text-sm font-medium text-foreground">Total Applications</p>
            <p className="text-xs text-muted-foreground mt-0.5">Across all roles</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">{appliedCount}</p>
            <p className="mt-1 text-sm font-medium text-foreground">Candidate Applied</p>
            <p className="text-xs text-muted-foreground mt-0.5">Awaiting employer review</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">{shortlistedCount}</p>
            <p className="mt-1 text-sm font-medium text-foreground">Shortlisted</p>
            <p className="text-xs text-muted-foreground mt-0.5">Selected by employers</p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">{mutualCount}</p>
            <p className="mt-1 text-sm font-medium text-foreground">Mutual Fits</p>
            <p className="text-xs text-muted-foreground mt-0.5">Ready for handoff</p>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="mt-8 rounded-3xl border border-border bg-card p-5">
          <form method="GET" className="flex flex-wrap items-center gap-4">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                name="q"
                defaultValue={filters.q ?? ""}
                placeholder="Search candidate, job, or company..."
                className="w-full rounded-full border border-border bg-background pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>

            {/* Status Select */}
            <div className="flex items-center gap-2">
              <label htmlFor="status" className="text-xs font-medium text-muted-foreground">
                Status:
              </label>
              <select
                id="status"
                name="status"
                defaultValue={filters.status ?? "all"}
                className="rounded-full border border-border bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="all">All statuses</option>
                <option value="candidate_interested">Candidate Applied</option>
                <option value="employer_shortlisted">Shortlisted</option>
                <option value="mutual_fit">Mutual Fit</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <button
              type="submit"
              className="rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 transition"
            >
              Filter
            </button>

            {(filters.status || filters.q || filters.job_id) && (
              <Link
                href="/admin/applications"
                className="text-xs text-muted-foreground hover:text-foreground underline"
              >
                Clear filters
              </Link>
            )}
          </form>
        </div>

        {/* Applications Table */}
        <div className="mt-6">
          {errorMsg ? (
            <div className="rounded-3xl border border-rose-500/20 bg-rose-500/10 p-8 text-center text-rose-600 dark:text-rose-400">
              <p className="font-semibold">Unable to load applications</p>
              <p className="mt-1 text-sm">{errorMsg}</p>
            </div>
          ) : applications.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center">
              <Briefcase className="mx-auto h-12 w-12 text-muted-foreground/40 mb-3" />
              <p className="text-lg font-medium text-foreground">No applications found</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {filters.status || filters.q
                  ? "Try adjusting your search criteria or clearing filters."
                  : "Applications submitted by candidates will appear here."}
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-3xl border border-border bg-card">
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/40">
                    <tr>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Candidate</th>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Job & Company</th>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Status</th>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Fit Score</th>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Applied Date</th>
                      <th className="px-5 py-4 font-medium text-muted-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {applications.map((app) => {
                      const cand = app.candidate_profile;
                      const candUser = cand?.user;
                      const candId = cand?.id || app.candidate_profile_id;
                      const candName = candUser?.full_name || cand?.full_name || app.candidate_profiles?.full_name || "Candidate";
                      const candEmail = candUser?.email || cand?.email || app.candidate_profiles?.email || "";
                      const job = app.job || app.jobs;
                      const jobTitle = job?.title || app.job_title || "Job Posting";
                      const companyName = job?.companies?.name || (job as any)?.company?.name || (job as any)?.company_name || "Company";
                      const statusBadge = applicationStatusBadge(app.status);
                      const appliedDate = app.applied_at || app.created_at;

                      return (
                        <tr key={app.id} className="align-top hover:bg-muted/20 transition-colors">
                          {/* Candidate column */}
                          <td className="px-5 py-4">
                            {candId ? (
                              <Link
                                href={`/admin/candidates/${candId}`}
                                className="font-medium text-foreground hover:text-primary hover:underline inline-flex items-center gap-1.5"
                              >
                                {candName}
                              </Link>
                            ) : (
                              <span className="font-medium text-foreground">{candName}</span>
                            )}
                            {candEmail && (
                              <p className="mt-0.5 text-xs text-muted-foreground">{candEmail}</p>
                            )}
                          </td>

                          {/* Job & Company column */}
                          <td className="px-5 py-4">
                            <p className="font-medium text-foreground">{jobTitle}</p>
                            <p className="mt-0.5 text-xs text-muted-foreground">{companyName}</p>
                          </td>

                          {/* Status Badge */}
                          <td className="px-5 py-4">
                            <span
                              className={`rounded-full border px-3 py-0.5 text-xs font-medium ${statusBadge.bg}`}
                            >
                              {statusBadge.label}
                            </span>
                          </td>

                          {/* Match / Fit Score */}
                          <td className="px-5 py-4">
                            <span className="font-semibold text-foreground">
                              {app.match_score ?? 0}%
                            </span>
                          </td>

                          {/* Applied Date */}
                          <td className="px-5 py-4 whitespace-nowrap text-muted-foreground">
                            {formatDate(appliedDate)}
                          </td>

                          {/* Actions */}
                          <td className="px-5 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-3 text-xs">
                              {candId && (
                                <Link
                                  href={`/admin/candidates/${candId}`}
                                  className="inline-flex items-center gap-1 font-medium text-foreground hover:text-primary underline"
                                >
                                  <User className="h-3 w-3" />
                                  Profile
                                </Link>
                              )}
                              {candId && (
                                <a
                                  href={`/api/admin/candidates/${candId}/resume`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1 font-medium text-primary hover:text-primary/80 underline"
                                >
                                  <FileText className="h-3 w-3" />
                                  Resume
                                </a>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
    </AdminShell>
  );
}
