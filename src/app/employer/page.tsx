import Link from "next/link";
import { ArrowRight, Briefcase, Sparkles, Users } from "lucide-react";
import {
  EmployerMatchCard,
  JobCard,
} from "@/components/employer/EmployerMatchCard";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function EmployerDashboardPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("*")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (!company) {
    redirect("/employer/onboarding");
  }

  if (!isCompanyProfileComplete(company)) {
    redirect("/employer/onboarding");
  }

  const { data: jobs } = await supabase
    .from("jobs")
    .select("*")
    .eq("company_id", company.id)
    .order("created_at", { ascending: false })
    .limit(3);

  const { count: jobCount } = await supabase
    .from("jobs")
    .select("*", { count: "exact", head: true })
    .eq("company_id", company.id);

  const { data: matches } = await supabase
    .from("matches")
    .select(
      `
      *,
      jobs!inner ( id, title, posted_by ),
      candidate_profiles (
        id, headline, skills, experience_level,
        profiles ( full_name, email )
      )
    `,
    )
    .eq("jobs.posted_by", profile.id)
    .eq("visible_to_employer", true)
    .order("match_score", { ascending: false })
    .limit(3);

  const { count: matchCount } = await supabase
    .from("matches")
    .select("*, jobs!inner(posted_by)", { count: "exact", head: true })
    .eq("jobs.posted_by", profile.id)
    .eq("visible_to_employer", true);

  const { count: shortlistedCount } = await supabase
    .from("matches")
    .select("*, jobs!inner(posted_by)", { count: "exact", head: true })
    .eq("jobs.posted_by", profile.id)
    .eq("visible_to_employer", true)
    .eq("status", "employer_shortlisted");

  const activeJobs =
    jobs?.filter((j) => j.status === "active").length ?? 0;
  const shortlisted = shortlistedCount ?? 0;

  return (
    <EmployerShell name={profile.full_name} activePath="/employer">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              {company.name}
            </h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Your posted roles and matched candidates for global remote tech
              hiring.
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

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Briefcase className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{jobCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Total roles</p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{matchCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Matched candidates</p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <Users className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{shortlisted}</p>
            <p className="mt-1 text-sm text-muted-foreground">Shortlisted</p>
          </div>
        </div>

        <section className="mt-12 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="flex items-center justify-between gap-4">
              <h2 className="display-headline text-2xl">Matched candidates</h2>
              {matchCount ? (
                <Link
                  href="/employer/matches"
                  className="text-sm font-medium text-muted-foreground hover:text-foreground"
                >
                  View all
                </Link>
              ) : null}
            </div>
            <div className="mt-6 space-y-4">
              {matches?.length ? (
                matches.map((match) => (
                  <EmployerMatchCard key={match.id} match={match} />
                ))
              ) : (
                <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
                  <p className="text-lg font-medium">No matched candidates yet</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    People Prime is reviewing candidates for your roles. Approved
                    matches will appear here within 24 hours.
                  </p>
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-6">
            <div className="rounded-3xl border border-border bg-card p-6">
              <p className="font-mono text-xs uppercase tracking-widest text-primary">
                Company
              </p>
              <h3 className="display-headline mt-4 text-3xl">{company.name}</h3>
              {company.industry && (
                <p className="mt-2 text-sm text-muted-foreground">
                  {company.industry} · {company.hq_city}
                </p>
              )}
              {company.description && (
                <p className="mt-4 line-clamp-4 text-sm text-muted-foreground">
                  {company.description}
                </p>
              )}
              <div className="mt-6 flex flex-wrap gap-2">
                {company.domain_verified && (
                  <span className="rounded-full border border-border px-3 py-1 text-xs">
                    Domain verified
                  </span>
                )}
                {company.badge_remote_first && (
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">
                    Remote-first
                  </span>
                )}
                {company.badge_visa_sponsor && (
                  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary">
                    Visa sponsor
                  </span>
                )}
              </div>
              <Link
                href="/employer/company"
                className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-full border border-border py-3 text-sm font-medium transition-colors hover:bg-muted"
              >
                Edit company profile
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="rounded-3xl border border-border bg-card p-6">
              <div className="flex items-center justify-between gap-4">
                <h3 className="font-semibold">Recent roles</h3>
                <Link
                  href="/employer/jobs"
                  className="text-sm font-medium text-muted-foreground hover:text-foreground"
                >
                  View all
                </Link>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {activeJobs} active
              </p>
              <div className="mt-4 space-y-4">
                {jobs?.length ? (
                  jobs.map((job) => <JobCard key={job.id} job={job} />)
                ) : (
                  <p className="text-sm text-muted-foreground">No roles yet.</p>
                )}
              </div>
            </div>
          </aside>
        </section>
      </main>
    </EmployerShell>
  );
}
