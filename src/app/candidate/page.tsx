import Link from "next/link";
import { ArrowRight, Briefcase, FileText, Sparkles } from "lucide-react";
import { CandidateMatchCard } from "@/components/candidate/CandidateMatchCard";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function CandidateDashboardPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: candidateProfile } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("user_id", profile.id)
    .maybeSingle();

  if (!isCandidateProfileComplete(candidateProfile)) {
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
    .order("match_score", { ascending: false })
    .limit(3);

  const { count: matchCount } = await supabase
    .from("matches")
    .select("*", { count: "exact", head: true });

  const interestedCount =
    matches?.filter((m) => m.status === "candidate_interested").length ?? 0;

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate">
      <main className={appMainClass}>
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Welcome back,{" "}
              <span className="italic text-primary">
                {profile.full_name.split(" ")[0] || "there"}.
              </span>
            </h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Your matched remote tech roles, profile status, and next steps.
            </p>
          </div>
          <Link
            href="/candidate/profile"
            className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
          >
            Edit profile
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{matchCount ?? 0}</p>
            <p className="mt-1 text-sm text-muted-foreground">Total matches</p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <Briefcase className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{interestedCount}</p>
            <p className="mt-1 text-sm text-muted-foreground">Roles you liked</p>
          </div>
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <FileText className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">
              {candidateProfile?.profile_completeness ?? 0}%
            </p>
            <p className="mt-1 text-sm text-muted-foreground">Profile complete</p>
          </div>
        </div>

        <section className="mt-12 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <div className="flex items-center justify-between gap-4">
              <h2 className="display-headline text-2xl">Recent matches</h2>
              <Link
                href="/candidate/matches"
                className="text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                View all
              </Link>
            </div>
            <div className="mt-6 space-y-4">
              {matches?.length ? (
                matches.map((match) => (
                  <CandidateMatchCard key={match.id} match={match} />
                ))
              ) : (
                <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
                  <p className="text-lg font-medium">No matches yet</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    We&apos;re scanning active roles. Check back soon.
                  </p>
                </div>
              )}
            </div>
          </div>

          <aside className="rounded-3xl border border-border bg-card p-6">
            <p className="font-mono text-xs uppercase tracking-widest text-primary">
              Your profile
            </p>
            <h3 className="display-headline mt-4 text-3xl">
              {candidateProfile?.headline}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {candidateProfile?.current_title} · {candidateProfile?.us_state}
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              {candidateProfile?.skills?.slice(0, 8).map((skill: string) => (
                <span
                  key={skill}
                  className="rounded-full border border-border px-3 py-1 text-xs"
                >
                  {skill}
                </span>
              ))}
            </div>

            <dl className="mt-8 space-y-4 border-t border-border pt-6 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Availability</dt>
                <dd className="font-medium capitalize">
                  {candidateProfile?.availability_status?.replace(/_/g, " ")}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Work type</dt>
                <dd className="font-medium capitalize">
                  {candidateProfile?.preferred_work_type}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Resume</dt>
                <dd className="font-medium text-primary">Uploaded</dd>
              </div>
            </dl>

            <Link
              href="/candidate/profile"
              className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-full border border-border py-3 text-sm font-medium transition-colors hover:bg-muted"
            >
              Update profile
              <ArrowRight className="h-4 w-4" />
            </Link>
          </aside>
        </section>
      </main>
    </CandidateShell>
  );
}
