import Link from "next/link";
import { Suspense } from "react";
import { ArrowRight } from "lucide-react";
import { EmployerMatchCard } from "@/components/employer/EmployerMatchCard";
import { EmployerMatchesFilters } from "@/components/employer/EmployerMatchesFilters";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { companiesApi, jobsApi, matchingApi } from "@/lib/api";
import type { MatchStatus } from "@/lib/types";
import { redirect } from "next/navigation";

const matchStatuses: MatchStatus[] = [
  "suggested",
  "candidate_interested",
  "employer_shortlisted",
  "mutual_fit",
  "rejected",
];

export default async function EmployerMatchesPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; job?: string }>;
}) {
  const { status, job } = await searchParams;
  const { profile } = await requireRole("employer");
  const token = await getAccessToken();

  let company = null;
  try {
    company = await companiesApi.getMyCompany({ token });
  } catch (err) {
    console.error("Failed to load company from Django:", err);
  }

  if (!company || !isCompanyProfileComplete(company)) {
    redirect("/employer/onboarding");
  }

  let jobs: Array<{ id: string; title: string }> = [];
  try {
    const djangoJobs = await jobsApi.getMyJobs({ token });
    if (djangoJobs) {
      jobs = djangoJobs.map((j) => ({ id: j.id, title: j.title }));
    }
  } catch (err) {
    console.error("Failed to load employer jobs from Django:", err);
  }

  let matches: any[] = [];
  let totalCount = 0;
  let shortlistedCount = 0;
  let interestedCount = 0;

  try {
    const allEmployerMatches = await matchingApi.listMatches({}, { token });
    if (allEmployerMatches) {
      totalCount = allEmployerMatches.length;
      shortlistedCount = allEmployerMatches.filter((m) => m.status === "employer_shortlisted").length;
      interestedCount = allEmployerMatches.filter((m) => m.status === "candidate_interested").length;

      let filtered = allEmployerMatches;
      if (status && status !== "all" && matchStatuses.includes(status as MatchStatus)) {
        filtered = filtered.filter((m) => m.status === status);
      }
      if (job && job !== "all") {
        filtered = filtered.filter((m) => m.job_id === job || m.job?.id === job || m.jobs?.id === job);
      }
      matches = filtered;
    }
  } catch (err) {
    console.error("Failed to load employer matches from Django:", err);
  }

  return (
    <EmployerShell name={profile.full_name} activePath="/employer/matches">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Matched <span className="italic text-foreground">candidates.</span>
            </h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Review matched talent for your remote tech roles. People Prime
              vets high-confidence matches before they appear here.
            </p>
          </div>
          <Link
            href="/employer/jobs/new"
            className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Post a role
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{totalCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Total matches</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{interestedCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Interested</p>
          </div>
          <div className="rounded-2xl border border-border bg-card px-5 py-4">
            <p className="text-2xl font-semibold">{shortlistedCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Shortlisted</p>
          </div>
        </div>

        <div className="mt-8">
          <Suspense fallback={<div className="h-20" />}>
            <EmployerMatchesFilters jobs={jobs} />
          </Suspense>
        </div>

        <div className="mt-8 space-y-4">
          {matches.length ? (
            matches.map((match: any) => <EmployerMatchCard key={match.id} match={match} />)
          ) : (
            <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
              <p className="text-lg font-medium">No matches in this view</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {totalCount
                  ? "Try a different filter or check another role."
                  : "People Prime is reviewing candidates for your roles. Approved matches will appear here."}
              </p>
              {!totalCount && (
                <Link
                  href="/employer/jobs/new"
                  className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
                >
                  Post a role
                  <ArrowRight className="h-4 w-4" />
                </Link>
              )}
            </div>
          )}
        </div>
      </main>
    </EmployerShell>
  );
}
