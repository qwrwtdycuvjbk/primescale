import { RecruiterMatchReviewCard } from "@/components/admin/RecruiterMatchReviewCard";
import { AdminShell } from "@/components/admin/AdminShell";
import { requireAdmin } from "@/lib/auth";
import { MIN_MATCH_SCORE } from "@/lib/recruiter-alert";
import { getServiceClient } from "@/lib/supabase/service";
import { redirect } from "next/navigation";

export default async function AdminMatchesPage() {
  const { profile } = await requireAdmin();
  const supabase = getServiceClient();
  if (!supabase) redirect("/");

  const { data: pendingMatches } = await supabase
    .from("matches")
    .select(
      `
      *,
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
    .order("match_score", { ascending: false });

  const { count: pendingCount } = await supabase
    .from("matches")
    .select("*", { count: "exact", head: true })
    .eq("visible_to_employer", false)
    .gte("match_score", MIN_MATCH_SCORE)
    .neq("status", "rejected");

  return (
    <AdminShell name={profile.full_name} activePath="/admin/matches">
      <main className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <h1 className="display-headline text-4xl sm:text-5xl">
          Match <span className="italic text-primary">review.</span>
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
            pendingMatches.map((match) => (
              <RecruiterMatchReviewCard key={match.id} match={match} />
            ))
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
