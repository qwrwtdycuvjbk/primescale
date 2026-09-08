import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { JobCard } from "@/components/employer/EmployerMatchCard";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { createClient } from "@/lib/supabase/server";
import { companiesApi, jobsApi } from "@/lib/api";
import type { Job } from "@/lib/types";
import { redirect } from "next/navigation";

export default async function EmployerJobsPage() {
  const { profile } = await requireRole("employer");
  const token = await getAccessToken();

  let company = null;
  try {
    company = await companiesApi.getMyCompany({ token });
  } catch {
    // Fall back to Supabase
  }

  const supabase = await createClient();

  if (!company) {
    const { data: sbCompany } = await supabase
      .from("companies")
      .select("*")
      .eq("owner_id", profile.id)
      .maybeSingle();
    company = sbCompany;
  }

  if (!company || !isCompanyProfileComplete(company)) {
    redirect("/employer/onboarding");
  }

  let jobs: Job[] | null = null;
  try {
    const djangoJobs = await jobsApi.getMyJobs({ token });
    if (djangoJobs) {
      jobs = djangoJobs as unknown as Job[];
    }
  } catch {
    // Fall back to Supabase
  }

  if (!jobs) {
    const { data: sbJobs } = await supabase
      .from("jobs")
      .select("*")
      .eq("company_id", company.id)
      .order("created_at", { ascending: false });
    jobs = sbJobs;
  }

  return (
    <EmployerShell name={profile.full_name} activePath="/employer/jobs">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl">Your roles</h1>
            <p className="mt-3 text-muted-foreground">
              Manage drafts, active posts, and duplicates. Active roles expire
              after 30 days.
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

        <div className="mt-10 space-y-4">
          {jobs?.length ? (
            jobs.map((job) => <JobCard key={job.id} job={job} />)
          ) : (
            <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
              <p className="text-lg font-medium">No roles posted yet</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Create your first remote tech role to start matching.
              </p>
              <Link
                href="/employer/jobs/new"
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground"
              >
                Post a role
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          )}
        </div>
      </main>
    </EmployerShell>
  );
}
