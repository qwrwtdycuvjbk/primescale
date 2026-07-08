import Link from "next/link";
import { ArrowRight } from "lucide-react";
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

type StatCardProps = {
  label: string;
  value: number;
  href: string;
  detail?: string;
  highlight?: boolean;
};

function StatCard({ label, value, href, detail, highlight }: StatCardProps) {
  return (
    <Link
      href={href}
      className={`group rounded-2xl border bg-card px-5 py-4 transition hover:-translate-y-0.5 ${
        highlight && value > 0
          ? "border-primary/40 shadow-sm"
          : "border-border"
      }`}
    >
      <p className="text-3xl font-semibold">{value}</p>
      <p className="mt-1 text-sm font-medium">{label}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
      <span className="mt-3 inline-flex items-center gap-1 text-sm text-primary opacity-0 transition group-hover:opacity-100">
        View
        <ArrowRight className="h-3.5 w-3.5" />
      </span>
    </Link>
  );
}

type PreviewListProps = {
  title: string;
  href: string;
  emptyMessage: string;
  children: React.ReactNode;
};

function PreviewList({ title, href, emptyMessage, children }: PreviewListProps) {
  return (
    <section className="rounded-3xl border border-border bg-card p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Link href={href} className="text-sm font-medium text-primary hover:underline">
          View all
        </Link>
      </div>
      <div className="mt-4">{children}</div>
      {!children && (
        <p className="mt-4 text-sm text-muted-foreground">{emptyMessage}</p>
      )}
    </section>
  );
}

export default async function AdminDashboardPage() {
  const { profile } = await requireAdmin();
  const stats = await loadAdminDashboardStats();

  const needsAttention =
    stats.pendingMatches +
    stats.pendingHandoffs +
    stats.activeJobsWithNoMatches;

  return (
    <AdminShell name={profile.full_name} activePath="/admin">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          <span className="italic text-primary">Dashboard.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          What needs attention today — pending reviews, handoffs, new signups, and
          gaps in matching.
        </p>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/admin/candidates/new"
            className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Add candidate
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {needsAttention > 0 && (
          <div className="mt-8 rounded-2xl border border-primary/30 bg-primary/5 px-5 py-4">
            <p className="font-medium text-primary">
              {needsAttention} item{needsAttention === 1 ? "" : "s"} need attention
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Review matches, coordinate handoffs, or check roles with no candidates yet.
            </p>
          </div>
        )}

        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <StatCard
            label="Pending match reviews"
            value={stats.pendingMatches}
            href="/admin/matches"
            detail="85%+ score, not yet released"
            highlight
          />
          <StatCard
            label="Pending handoffs"
            value={stats.pendingHandoffs}
            href="/admin/handoffs"
            detail="Mutual fit awaiting outreach"
            highlight
          />
          <StatCard
            label="New candidates this week"
            value={stats.newCandidatesThisWeek}
            href="/admin/candidates"
            detail="Signed up since Monday"
          />
          <StatCard
            label="New employers this week"
            value={stats.newEmployersThisWeek}
            href="/admin/jobs"
            detail="Signed up since Monday"
          />
          <StatCard
            label="Active jobs with no matches"
            value={stats.activeJobsWithNoMatches}
            href="/admin/jobs?status=active"
            detail="May need manual sourcing"
            highlight
          />
          <StatCard
            label="Incomplete profiles"
            value={stats.incompleteProfiles}
            href="/admin/candidates?complete=no"
            detail="Blocking automatic matching"
            highlight
          />
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <PreviewList
            title="Match review queue"
            href="/admin/matches"
            emptyMessage="No high-confidence matches waiting for approval."
          >
            {stats.pendingMatchPreviews.length > 0 ? (
              <ul className="divide-y divide-border">
                {stats.pendingMatchPreviews.map((match) => (
                  <li key={match.id} className="flex items-start justify-between gap-4 py-3 first:pt-0">
                    <div>
                      <p className="font-medium">
                        {match.candidateName} → {match.jobTitle}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">{match.companyName}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-700 dark:text-amber-300">
                      {match.matchScore}%
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </PreviewList>

          <PreviewList
            title="Handoff queue"
            href="/admin/handoffs"
            emptyMessage="No pending handoffs right now."
          >
            {stats.pendingHandoffPreviews.length > 0 ? (
              <ul className="divide-y divide-border">
                {stats.pendingHandoffPreviews.map((handoff) => (
                  <li key={handoff.id} className="py-3 first:pt-0">
                    <p className="font-medium">
                      {handoff.candidateName} → {handoff.jobTitle}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">{handoff.companyName}</p>
                  </li>
                ))}
              </ul>
            ) : null}
          </PreviewList>

          <PreviewList
            title="Active roles with no matches"
            href="/admin/jobs?status=active"
            emptyMessage="Every active role has at least one match."
          >
            {stats.unmatchedJobPreviews.length > 0 ? (
              <ul className="divide-y divide-border">
                {stats.unmatchedJobPreviews.map((job) => (
                  <li key={job.id} className="py-3 first:pt-0">
                    <p className="font-medium">{job.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {job.companyName} · Posted {formatDate(job.postedAt)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : null}
          </PreviewList>

          <PreviewList
            title="Incomplete candidate profiles"
            href="/admin/candidates?complete=no"
            emptyMessage="All candidates have completed their profiles."
          >
            {stats.incompleteProfilePreviews.length > 0 ? (
              <ul className="divide-y divide-border">
                {stats.incompleteProfilePreviews.map((candidate) => (
                  <li key={candidate.id} className="py-3 first:pt-0">
                    <p className="font-medium">{candidate.name}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {candidate.email || "No email"} · Signed up {formatDate(candidate.signedUpAt)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : null}
          </PreviewList>
        </div>
      </main>
    </AdminShell>
  );
}
