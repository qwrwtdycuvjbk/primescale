import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Briefcase,
  CheckCircle2,
  FileText,
  Globe,
  Layers,
  Search,
  Shield,
  Sparkles,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";
import { loadAdminDashboardStats } from "@/lib/admin-dashboard";

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function StatCard({
  label,
  value,
  href,
  detail,
  subDetail,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  href: string;
  detail?: string;
  subDetail?: string;
  icon?: any;
}) {
  return (
    <Link
      href={href}
      className="group rounded-3xl border border-border bg-card p-5 transition hover:-translate-y-0.5 hover:shadow-sm"
    >
      <div className="flex items-center justify-between">
        <p className="text-3xl font-bold tracking-tight text-foreground">{value}</p>
        {Icon && <Icon className="h-5 w-5 text-muted-foreground/60 group-hover:text-primary transition-colors" />}
      </div>
      <p className="mt-2 text-sm font-semibold text-foreground">{label}</p>
      {detail && <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>}
      {subDetail && <p className="mt-1 text-xs text-primary font-medium">{subDetail}</p>}
    </Link>
  );
}

export default async function AdminDashboardPage() {
  const { profile } = await requireAdmin();
  const stats = await loadAdminDashboardStats();

  return (
    <AdminShell name={profile.full_name} activePath="/admin">
      <main className={appMainClass}>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="display-headline text-4xl sm:text-5xl">
                Platform <span className="italic text-foreground">monitor.</span>
              </h1>
              <span className="rounded-full bg-primary/10 text-primary border border-primary/20 px-3 py-0.5 text-xs font-bold uppercase tracking-wider">
                Read-Only
              </span>
            </div>
            <p className="mt-2 text-muted-foreground max-w-2xl">
              System-wide observability, candidate metrics, job pipelines, and application telemetry.
            </p>
          </div>
        </div>

        {/* 1. Candidate Platform Metrics */}
        <div className="mt-10">
          <div className="flex items-center gap-2 mb-4">
            <Users className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
              Candidate Pool Metrics
            </h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Candidates"
              value={stats.totalCandidates ?? 0}
              href="/admin/candidates"
              detail="Total talent registered"
              subDetail={`+${stats.newCandidatesThisWeek ?? 0} this week`}
              icon={Users}
            />
            <StatCard
              label="Completed Profiles"
              value={stats.completedProfiles ?? 0}
              href="/admin/candidates?complete=yes"
              detail="100% complete dossiers"
              icon={CheckCircle2}
            />
            <StatCard
              label="Incomplete Profiles"
              value={stats.incompleteProfiles ?? 0}
              href="/admin/candidates?complete=no"
              detail="Awaiting onboarding"
              icon={Activity}
            />
            <StatCard
              label="Resumes on File"
              value={stats.candidatesWithResume ?? 0}
              href="/admin/candidates?resume=yes"
              detail="Stored in private S3"
              icon={FileText}
            />
            <StatCard
              label="Available Candidates"
              value={stats.candidatesAvailable ?? 0}
              href="/admin/candidates?availability=actively_looking"
              detail="Actively looking / open"
              icon={UserCheck}
            />
            <StatCard
              label="Open to Matching"
              value={stats.candidatesOpenToMatching ?? 0}
              href="/admin/candidates?matching=yes"
              detail="Active in match engine"
              icon={Sparkles}
            />
            <StatCard
              label="Candidate Accounts"
              value={stats.totalCandidateAccounts ?? 0}
              href="/admin/candidates"
              detail="Auth accounts"
              icon={Users}
            />
            <StatCard
              label="Employer Accounts"
              value={stats.totalEmployerAccounts ?? 0}
              href="/admin/employers"
              detail="Hiring companies"
              subDetail={`+${stats.newEmployersThisWeek ?? 0} this week`}
              icon={Briefcase}
            />
          </div>
        </div>

        {/* 2. Jobs, Applications & Matching Metrics */}
        <div className="mt-10">
          <div className="flex items-center gap-2 mb-4">
            <Layers className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
              Jobs, Applications & Intelligence
            </h2>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            <StatCard
              label="Internal Active Jobs"
              value={stats.activeJobs ?? 0}
              href="/admin/jobs?status=active"
              detail={`${stats.totalInternalJobs ?? 0} total internal`}
              icon={Briefcase}
            />
            <StatCard
              label="External Sourced Jobs"
              value={stats.totalExternalJobs ?? 0}
              href="/admin/job-leads"
              detail="People Prime / APIs"
              icon={Globe}
            />
            <StatCard
              label="Total Applications"
              value={stats.totalApplications ?? 0}
              href="/admin/applications"
              detail="Candidate job intents"
              icon={Layers}
            />
            <StatCard
              label="Mutual Fits"
              value={stats.mutualFit ?? 0}
              href="/admin/applications?status=mutual_interest"
              detail="Ready for direct hire"
              icon={CheckCircle2}
            />
            <StatCard
              label="Active Algorithmic Matches"
              value={stats.totalMatches ?? 0}
              href="/admin/matches"
              detail="AI computed candidate fits"
              icon={Sparkles}
            />
            <StatCard
              label="High Fit Scores"
              value={stats.highConfidenceMatches ?? 0}
              href="/admin/matches"
              detail="Tier-1 talent matches (75%+)"
              icon={Sparkles}
            />
            <StatCard
              label="Pending Match Review"
              value={stats.pendingMatches ?? 0}
              href="/admin/matches"
              detail="Unreleased pairings"
              icon={Shield}
            />
          </div>
        </div>

        {/* 3. Monitoring Queues / Previews */}
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Top Matches Monitor */}
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-foreground">Top Algorithmic Matches</h3>
                <p className="text-xs text-muted-foreground">High scoring candidate-job alignments</p>
              </div>
              <Link
                href="/admin/matches"
                className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              >
                View all ({stats.totalMatches ?? 0})
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {stats.pendingMatchPreviews && stats.pendingMatchPreviews.length > 0 ? (
              <div className="divide-y divide-border">
                {stats.pendingMatchPreviews.map((p) => (
                  <div key={p.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-semibold text-sm text-foreground">{p.candidateName}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.jobTitle} - <span className="font-medium">{p.companyName}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="rounded-full bg-primary/10 text-primary px-2.5 py-0.5 text-xs font-bold">
                        {p.matchScore}% fit
                      </span>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground capitalize">
                        {p.status.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-6 text-center">No active matches recorded.</p>
            )}
          </div>

          {/* Recent Candidates Monitor */}
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-foreground">Recent Candidate Signups</h3>
                <p className="text-xs text-muted-foreground">Latest registered talent on the platform</p>
              </div>
              <Link
                href="/admin/candidates"
                className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              >
                View registry ({stats.totalCandidates ?? 0})
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {stats.recentCandidatePreviews && stats.recentCandidatePreviews.length > 0 ? (
              <div className="divide-y divide-border">
                {stats.recentCandidatePreviews.map((c) => (
                  <div key={c.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                    <div>
                      <Link
                        href={`/admin/candidates/${c.id}`}
                        className="font-semibold text-sm text-foreground hover:text-primary hover:underline"
                      >
                        {c.name}
                      </Link>
                      <p className="text-xs text-muted-foreground">
                        {c.currentTitle} - <span className="font-mono">{c.email}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 text-xs">
                      <span className="rounded-full bg-muted px-2.5 py-0.5 font-medium text-foreground">
                        {c.completeness}% profile
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-6 text-center">No candidates recorded.</p>
            )}
          </div>

          {/* Unmatched Jobs Monitor */}
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-foreground">Active Jobs with 0 Matches</h3>
                <p className="text-xs text-muted-foreground">Jobs needing talent sourcing</p>
              </div>
              <Link
                href="/admin/jobs?status=active"
                className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              >
                View jobs
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {stats.unmatchedJobPreviews && stats.unmatchedJobPreviews.length > 0 ? (
              <div className="divide-y divide-border">
                {stats.unmatchedJobPreviews.map((j) => (
                  <div key={j.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-semibold text-sm text-foreground">{j.title}</p>
                      <p className="text-xs text-muted-foreground">{j.companyName}</p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      Posted {formatDate(j.postedAt)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-6 text-center">All active jobs have candidates.</p>
            )}
          </div>

          {/* Incomplete Profiles Monitor */}
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-foreground">Incomplete Onboarding Signups</h3>
                <p className="text-xs text-muted-foreground">Candidates who have not completed profile</p>
              </div>
              <Link
                href="/admin/candidates?complete=no"
                className="text-xs font-semibold text-primary hover:underline inline-flex items-center gap-1"
              >
                View all ({stats.incompleteProfiles ?? 0})
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {stats.incompleteProfilePreviews && stats.incompleteProfilePreviews.length > 0 ? (
              <div className="divide-y divide-border">
                {stats.incompleteProfilePreviews.map((u) => (
                  <div key={u.id} className="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-semibold text-sm text-foreground">{u.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">{u.email}</p>
                    </div>
                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                      {formatDate(u.signedUpAt)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-6 text-center">All candidate profiles are complete.</p>
            )}
          </div>
        </div>
      </main>
    </AdminShell>
  );
}