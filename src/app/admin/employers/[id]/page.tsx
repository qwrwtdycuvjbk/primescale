import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  Calendar,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  Briefcase,
  Users,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { companiesApi, type DjangoAdminEmployerDetail } from "@/lib/api/companies";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default async function AdminEmployerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { profile: adminProfile } = await requireAdmin();
  const token = await getAccessToken();

  let employer: DjangoAdminEmployerDetail | null = null;
  let errorState: string | null = null;

  try {
    const data = await companiesApi.getAdminEmployer(id, { token });
    if (data && data.id) {
      employer = data;
    }
  } catch (err: any) {
    console.error("Failed to load employer detail:", err);
    errorState = err?.message || "Employer organization not found";
  }

  if (!employer || errorState) {
    return (
      <AdminShell name={adminProfile.full_name} activePath="/admin/employers">
        <main className={appMainClass}>
          <Link
            href="/admin/employers"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Employers
          </Link>

          <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center max-w-xl mx-auto">
            <Building2 className="mx-auto h-12 w-12 text-muted-foreground/40" />
            <h2 className="mt-4 text-xl font-semibold">Employer Not Found</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {errorState || "The requested employer profile could not be loaded or does not exist."}
            </p>
            <div className="mt-6">
              <Link
                href="/admin/employers"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
              >
                Return to Employer Registry
              </Link>
            </div>
          </div>
        </main>
      </AdminShell>
    );
  }

  const companyName = employer.name || employer.primary_contact_name || "Employer Account";
  const members = Array.isArray(employer.members) ? employer.members : [];
  const jobs = Array.isArray(employer.jobs) ? employer.jobs : [];

  return (
    <AdminShell name={adminProfile.full_name} activePath="/admin/employers">
      <main className={appMainClass}>
        {/* Back Link */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/admin/employers"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Employers
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Company / Employer ID:</span>
            <code className="rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">
              {employer.id}
            </code>
          </div>
        </div>

        {/* Header Profile Card */}
        <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary font-bold text-2xl">
                {companyName.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                    {companyName}
                  </h1>
                  {/* Account Status Badge */}
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold ${
                      employer.is_active
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        employer.is_active ? "bg-emerald-500" : "bg-red-500"
                      }`}
                    />
                    {employer.is_active ? "Active Organization" : "Inactive Organization"}
                  </span>
                  {employer.industry && (
                    <span className="rounded-full bg-muted px-3 py-0.5 text-xs font-medium text-muted-foreground">
                      {employer.industry}
                    </span>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  {employer.primary_contact_email && (
                    <span className="inline-flex items-center gap-1.5">
                      <Mail className="h-4 w-4 text-muted-foreground/70" />
                      {employer.primary_contact_email}
                    </span>
                  )}
                  {employer.location && (
                    <span className="inline-flex items-center gap-1.5">
                      <MapPin className="h-4 w-4 text-muted-foreground/70" />
                      {employer.location}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1.5">
                    <Calendar className="h-4 w-4 text-muted-foreground/70" />
                    Registered {formatDate(employer.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Actions Header */}
            <div className="flex flex-wrap items-center gap-3 lg:self-start">
              {employer.website && (
                <a
                  href={employer.website.startsWith("http") ? employer.website : `https://${employer.website}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted/40 transition shadow-sm"
                >
                  <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                  Visit Website
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </a>
              )}
            </div>
          </div>
        </div>

        {/* Content Grid */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Organization Details & Job Listings */}
          <div className="lg:col-span-2 space-y-8">
            {/* About / Description */}
            <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
              <h2 className="text-lg font-semibold text-foreground mb-4">About Employer / Organization</h2>
              {employer.description ? (
                <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {employer.description}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No company description or overview has been provided yet.
                </p>
              )}
            </div>

            {/* Posted Jobs Section */}
            <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Posted Job Openings</h2>
                  <p className="text-xs text-muted-foreground">All job listings published under this employer</p>
                </div>
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {jobs.length} Total
                </span>
              </div>

              {jobs.length > 0 ? (
                <div className="divide-y divide-border">
                  {jobs.map((job) => (
                    <div key={job.id} className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <p className="font-semibold text-sm text-foreground">{job.title}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span>{job.location || "Remote"}</span>
                          <span>•</span>
                          <span className="capitalize">{job.employment_type?.replace("_", " ") || "Full-time"}</span>
                          <span>•</span>
                          <span>Posted {formatDate(job.created_at)}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <span
                          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                            job.status === "active"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {job.status}
                        </span>
                        <Link
                          href={`/admin/jobs`}
                          className="text-xs font-medium text-foreground hover:text-primary underline"
                        >
                          View in Jobs
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-muted-foreground">
                  <Briefcase className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                  No jobs posted by this employer yet.
                </div>
              )}
            </div>

            {/* Team Members Section */}
            <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Team Members</h2>
                  <p className="text-xs text-muted-foreground">Authorized employer account users</p>
                </div>
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {members.length} Total
                </span>
              </div>

              {members.length > 0 ? (
                <div className="divide-y divide-border">
                  {members.map((m) => (
                    <div key={m.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-muted font-semibold text-xs text-foreground">
                          {(m.full_name || m.email || "U").charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-sm text-foreground">{m.full_name || "User"}</p>
                          <p className="text-xs text-muted-foreground font-mono">{m.email}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground capitalize">
                          {m.role || "Member"}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            m.is_active
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-red-500/10 text-red-600 dark:text-red-400"
                          }`}
                        >
                          {m.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-muted-foreground">
                  <Users className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                  No additional team members registered.
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Organization Metadata & Shortcuts */}
          <div className="space-y-8">
            {/* Organization Metadata */}
            <div className="rounded-3xl border border-border bg-card p-6">
              <h3 className="text-base font-semibold text-foreground mb-4">Company Overview</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between py-1 border-b border-border/50 text-xs">
                  <span className="text-muted-foreground">Primary Contact</span>
                  <span className="font-medium text-foreground">{employer.primary_contact_name || "—"}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-border/50 text-xs">
                  <span className="text-muted-foreground">Contact Email</span>
                  <span className="font-mono text-foreground">{employer.primary_contact_email || "—"}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-border/50 text-xs">
                  <span className="text-muted-foreground">Company Size</span>
                  <span className="font-medium text-foreground">{employer.company_size || "Not specified"}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-border/50 text-xs">
                  <span className="text-muted-foreground">Industry</span>
                  <span className="font-medium text-foreground">{employer.industry || "General"}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-border/50 text-xs">
                  <span className="text-muted-foreground">Profile Status</span>
                  <span className="font-medium text-foreground">
                    {employer.profile_complete ? "Complete" : "Incomplete"}
                  </span>
                </div>
                <div className="flex justify-between py-1 text-xs">
                  <span className="text-muted-foreground">Total Positions</span>
                  <span className="font-medium text-foreground">{employer.jobs_count ?? 0}</span>
                </div>
              </div>
            </div>

            {/* Admin Shortcuts */}
            <div className="rounded-3xl border border-border bg-card p-6">
              <h3 className="text-base font-semibold text-foreground mb-4">Admin Shortcuts</h3>
              <div className="space-y-2">
                <Link
                  href={`/admin/jobs?q=${encodeURIComponent(companyName)}`}
                  className="flex w-full items-center justify-between rounded-xl border border-border p-3 text-xs font-medium hover:bg-muted/40 transition"
                >
                  <span>Filter Company Jobs</span>
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </Link>
                <Link
                  href="/admin/matches"
                  className="flex w-full items-center justify-between rounded-xl border border-border p-3 text-xs font-medium hover:bg-muted/40 transition"
                >
                  <span>Review Match Pipeline</span>
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </main>
    </AdminShell>
  );
}