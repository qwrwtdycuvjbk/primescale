import { RecruiterMatchReviewCard } from "@/components/admin/RecruiterMatchReviewCard";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { MIN_MATCH_SCORE } from "@/lib/recruiter-alert";
import { getAdminClient } from "@/lib/supabase/admin";
import { matchingApi } from "@/lib/api";

export default async function AdminMatchesPage() {
  const { profile } = await requireAdmin();
  const token = await getAccessToken();

  let pendingMatches: any[] | null = null;
  let pendingCount = 0;

  try {
    const adminMatches = await matchingApi.listMatches({ visible_to_employer: false }, { token });
    if (adminMatches) {
      const filtered = adminMatches.filter(
        (m) => m.visible_to_employer === false && m.match_score >= MIN_MATCH_SCORE && m.status !== "rejected",
      );
      pendingMatches = filtered.slice(0, 50);
      pendingCount = filtered.length;
    }
  } catch {
    // Fall back to Supabase
  }

  if (!pendingMatches) {
    const supabase = await getAdminClient();
    const [{ data: sbPendingMatches }, { count: sbPendingCount }] = await Promise.all([
      supabase
        .from("matches")
        .select(
          `
        id,
        candidate_profile_id,
        job_id,
        match_score,
        match_reason,
        status,
        created_at,
        updated_at,
        jobs (
          title,
          companies ( name )
        ),
        candidate_profiles (
          headline,
          skills,
          profiles ( full_name, email )
        )
      `,
        )
        .eq("visible_to_employer", false)
        .gte("match_score", MIN_MATCH_SCORE)
        .neq("status", "rejected")
        .order("match_score", { ascending: false })
        .limit(50),
      supabase
        .from("matches")
        .select("id", { count: "exact", head: true })
        .eq("visible_to_employer", false)
        .gte("match_score", MIN_MATCH_SCORE)
        .neq("status", "rejected"),
    ]);

    pendingMatches = sbPendingMatches;
    pendingCount = sbPendingCount ?? 0;
  }

  return (
    <AdminShell name={profile.full_name} activePath="/admin/matches">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Match <span className="italic text-foreground">review.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          High-confidence matches ({MIN_MATCH_SCORE}%+) are held here until People
          Prime approves them. Employers only see candidates you release.
        </p>

        <div className="mt-8 rounded-2xl border border-border bg-card px-5 py-4">
          <p className="text-2xl font-semibold">{pendingCount ?? 0}</p>
          <p className="mt-1 text-sm text-muted-foreground">Pending recruiter review</p>
        </div>

        <div className="mt-8 space-y-4">
          {pendingMatches?.length ? (
            ((pendingMatches as any[]) ?? []).map((row: any) => {
              const jobRaw = row.jobs;
              const job = Array.isArray(jobRaw) ? jobRaw[0] : jobRaw;
              const companyRaw = job?.companies;
              const candidateRaw = row.candidate_profiles;
              const candidate = Array.isArray(candidateRaw)
                ? candidateRaw[0]
                : candidateRaw;
              const profileRaw = candidate?.profiles;

              const match = {
                ...row,
                jobs: job
                  ? {
                      ...job,
                      companies: Array.isArray(companyRaw)
                        ? companyRaw[0]
                        : companyRaw,
                    }
                  : undefined,
                candidate_profiles: candidate
                  ? {
                      ...candidate,
                      profiles: Array.isArray(profileRaw)
                        ? profileRaw[0]
                        : profileRaw,
                    }
                  : undefined,
              };

              return (
                <RecruiterMatchReviewCard key={row.id} match={match as never} />
              );
            })
          ) : (
            <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
              <p className="text-lg font-medium">No matches awaiting review</p>
              <p className="mt-2 text-sm text-muted-foreground">
                New {MIN_MATCH_SCORE}%+ matches will appear here and alert{" "}
                remote@people-prime.com.
              </p>
            </div>
          )}
        </div>
      </main>
    </AdminShell>
  );
}
