import { CandidateMatchCard, EmptyMatches } from "@/components/candidate/CandidateMatchCard";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { requireRole } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function CandidateMatchesPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: candidateProfile } = await supabase
    .from("candidate_profiles")
    .select("profile_complete, resume_url")
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
    .order("match_score", { ascending: false });

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate/matches">
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        <h1 className="display-headline text-4xl sm:text-5xl">
          Your <span className="italic text-primary">matches.</span>
        </h1>
        <p className="mt-3 text-muted-foreground">
          AI-matched US remote tech roles based on your profile and resume.
        </p>

        <div className="mt-10 space-y-4">
          {matches?.length ? (
            matches.map((match) => (
              <CandidateMatchCard key={match.id} match={match} />
            ))
          ) : (
            <EmptyMatches editProfileHref="/candidate/profile" />
          )}
        </div>
      </main>
    </CandidateShell>
  );
}
