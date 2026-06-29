import Link from "next/link";
import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { CandidateMatchCard } from "@/components/matches/MatchCard";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { buttonPrimaryClass } from "@/lib/ui";
import { redirect } from "next/navigation";

export default async function CandidateDashboardPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: candidateProfile } = await supabase
    .from("candidate_profiles")
    .select("id, profile_complete")
    .eq("user_id", profile.id)
    .maybeSingle();

  if (!candidateProfile?.profile_complete) {
    redirect("/candidate/onboarding");
  }

  const { data: matches } = await supabase
    .from("matches")
    .select(
      `
      *,
      jobs (
        id, title, description, tech_stack, salary_range, experience_level, role_type,
        companies ( name )
      )
    `,
    )
    .order("match_score", { ascending: false });

  return (
    <div className="min-h-screen bg-slate-50">
      <DashboardNav role="candidate" name={profile.full_name} />
      <main className="mx-auto max-w-4xl px-6 py-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">Your matches</h1>
            <p className="mt-2 text-slate-600">
              AI-matched US remote tech roles based on your profile.
            </p>
          </div>
          <Link href="/candidate/profile" className={buttonPrimaryClass}>
            Edit profile
          </Link>
        </div>

        <div className="mt-10 space-y-6">
          {matches?.length ? (
            matches.map((match) => (
              <CandidateMatchCard key={match.id} match={match} />
            ))
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
              <p className="text-lg font-medium text-slate-900">
                No matches yet
              </p>
              <p className="mt-2 text-slate-600">
                We&apos;re scanning active US tech roles. Check back soon or
                update your skills to improve matching.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
