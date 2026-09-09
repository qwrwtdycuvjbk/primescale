import { Suspense } from "react";
import { HandoffCard } from "@/components/admin/HandoffCard";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { AdminHandoffFilters } from "@/components/admin/AdminHandoffFilters";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { handoffsApi } from "@/lib/api";
import type { HandoffStatus } from "@/lib/types";

const handoffStatuses: HandoffStatus[] = [
  "pending",
  "contacted",
  "intro_made",
  "closed",
];

export default async function AdminHandoffsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const { status } = await searchParams;
  const { profile } = await requireAdmin();
  const token = await getAccessToken();

  let handoffs: any[] = [];
  let pendingCount = 0;

  try {
    const allHandoffs = await handoffsApi.listHandoffs(undefined, { token });
    if (allHandoffs) {
      pendingCount = allHandoffs.filter((h) => h.status === "pending").length;
      let filtered = allHandoffs;
      if (status && status !== "all" && handoffStatuses.includes(status as HandoffStatus)) {
        filtered = filtered.filter((h) => h.status === status);
      }
      handoffs = filtered;
    }
  } catch (err) {
    console.error("Failed to load handoffs from Django:", err);
  }

  return (
    <AdminShell name={profile.full_name} activePath="/admin/handoffs">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          People Prime <span className="italic text-foreground">handoffs.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Mutual-fit matches from People Remotely. Contact both parties, coordinate
          intros, and update queue status here.
        </p>

        <div className="mt-8 rounded-2xl border border-border bg-card px-5 py-4">
          <p className="text-2xl font-semibold">{pendingCount ?? 0}</p>
          <p className="mt-1 text-sm text-muted-foreground">Pending handoffs</p>
        </div>

        <div className="mt-8">
          <Suspense fallback={<div className="h-12" />}>
            <AdminHandoffFilters />
          </Suspense>
        </div>

        <div className="mt-8 space-y-4">
          {handoffs.length ? (
            handoffs.map((handoff) => (
              <HandoffCard key={handoff.id} handoff={handoff} />
            ))
          ) : (
            <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
              <p className="text-lg font-medium">No handoffs in this view</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Handoffs appear when an employer shortlists a candidate who already
                marked interest, or vice versa.
              </p>
            </div>
          )}
        </div>
      </main>
    </AdminShell>
  );
}
