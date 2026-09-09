import { CandidateMatchCard, EmptyMatches } from "@/components/candidate/CandidateMatchCard";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { createClient } from "@/lib/supabase/server";
import { candidatesApi, matchingApi } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function CandidateMatchesPage() {
  const { profile } = await requireRole("candidate");
  const token = await getAccessToken();

  let candidateProfile = null;
  try {
    candidateProfile = await candidatesApi.getMyProfile({ token });
  } catch {
    // Fall back to Supabase
  }

  const supabase = await createClient();

  if (!candidateProfile) {
    const { data: sbCandidateProfile } = await supabase
      .from("candidate_profiles")
      .select("profile_complete, resume_url")
      .eq("user_id", profile.id)
      .maybeSingle();
    candidateProfile = sbCandidateProfile;
  }

  if (!isCandidateProfileComplete(candidateProfile)) {
    redirect("/candidate/onboarding");
  }

  let matches: any[] | null = null;
  try {
    const djangoMatches = await matchingApi.listMatches({}, { token });
    if (djangoMatches) {
      matches = djangoMatches;
    }
  } catch {
    // Fall back to Supabase
  }

  if (!matches) {
    const { data: sbMatches } = await supabase
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
    matches = sbMatches;
  }

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate/matches">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Your <span className="italic text-foreground">matches.</span>
        </h1>
        <p className="mt-3 text-muted-foreground">
          Matched remote tech roles based on your profile and resume.
        </p>

        <div className="mt-10 space-y-4">
          {matches?.length ? (
            ((matches as any[]) ?? []).map((match: any) => (
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
