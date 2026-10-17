import Link from "next/link";
import { CandidateMatchCard, EmptyMatches } from "@/components/candidate/CandidateMatchCard";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { candidatesApi, matchingApi } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function CandidateMatchesPage() {
  const { profile } = await requireRole("candidate");
  const token = await getAccessToken();

  let candidateProfile = null;
  try {
    candidateProfile = await candidatesApi.getMyProfile({ token });
  } catch (err) {
    console.error("Failed to load candidate profile from Django:", err);
  }

  if (!candidateProfile || !isCandidateProfileComplete(candidateProfile)) {
    redirect("/candidate/onboarding");
  }

  let matches: any[] = [];
  let fetchError = false;
  try {
    const djangoMatches = await matchingApi.listMatches({}, { token });
    if (djangoMatches) {
      // Exclude external job board listings; candidate matches represent only verified first-party AI matches
      matches = djangoMatches.filter((m: any) => (m.job || m.jobs) && !m.is_external);
    }
  } catch (err) {
    console.error("Failed to load matches from Django:", err);
    fetchError = true;
  }

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate/matches">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Your <span className="italic text-foreground">matches.</span>
        </h1>
        <p className="mt-3 text-muted-foreground">
          Matched remote tech roles based on your verified skills, experience, and resume.
        </p>
        <p className="mt-1 text-xs text-muted-foreground/80">
          * AI matching indicates algorithmic qualification alignment; it does not guarantee an interview or employment.
        </p>

        <div className="mt-10 space-y-4">
          {fetchError ? (
            <div className="rounded-3xl border border-destructive/20 bg-destructive/10 p-8 text-center">
              <p className="text-lg font-medium text-destructive">Unable to load matches</p>
              <p className="mt-2 text-sm text-muted-foreground">
                We encountered an issue retrieving your matches. Please check your connection and try again.
              </p>
              <Link
                href="/candidate/matches"
                className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-90"
              >
                Retry
              </Link>
            </div>
          ) : matches.length ? (
            matches.map((match: any) => (
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
