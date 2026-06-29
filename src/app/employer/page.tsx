import Link from "next/link";
import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { EmployerMatchCard } from "@/components/matches/MatchCard";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { buttonPrimaryClass } from "@/lib/ui";
import { redirect } from "next/navigation";

export default async function EmployerDashboardPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("id, name")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (!company) {
    redirect("/employer/onboarding");
  }

  const { data: jobs } = await supabase
    .from("jobs")
    .select("id, title, status, created_at")
    .eq("company_id", company.id)
    .order("created_at", { ascending: false });

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
    .order("match_score", { ascending: false });

  return (
    <div className="min-h-screen bg-slate-50">
      <DashboardNav role="employer" name={profile.full_name} />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              {company.name}
            </h1>
            <p className="mt-2 text-slate-600">
              Your posted roles and AI-matched candidates.
            </p>
          </div>
          <Link href="/employer/jobs/new" className={buttonPrimaryClass}>
            Post a role
          </Link>
        </div>

        <section className="mt-12">
          <h2 className="text-xl font-semibold text-slate-900">Your roles</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {jobs?.length ? (
              jobs.map((job) => (
                <div
                  key={job.id}
                  className="rounded-2xl border border-slate-200 bg-white p-5"
                >
                  <p className="font-medium text-slate-900">{job.title}</p>
                  <p className="mt-2 text-sm capitalize text-slate-500">
                    {job.status}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-slate-600">No roles posted yet.</p>
            )}
          </div>
        </section>

        <section className="mt-12">
          <h2 className="text-xl font-semibold text-slate-900">
            Matched candidates
          </h2>
          <div className="mt-6 space-y-6">
            {matches?.length ? (
              matches.map((match) => (
                <EmployerMatchCard key={match.id} match={match} />
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
                <p className="text-lg font-medium text-slate-900">
                  No matched candidates yet
                </p>
                <p className="mt-2 text-slate-600">
                  Post a US remote tech role to start receiving matches.
                </p>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
