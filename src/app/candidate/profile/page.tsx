import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { CandidateProfileEditForm } from "@/components/candidate/CandidateProfileEditForm";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { requireRole } from "@/lib/auth";
import {
  isCandidateProfileComplete,
  mapCandidateRowToInput,
} from "@/lib/candidate-profile";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function CandidateProfilePage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: existing } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("user_id", profile.id)
    .maybeSingle();

  if (!isCandidateProfileComplete(existing)) {
    redirect("/candidate/onboarding");
  }

  const initialData = mapCandidateRowToInput(existing!, profile.phone);

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate/profile">
      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <Link
          href="/candidate"
          className="mb-6 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>

        <h1 className="display-headline text-4xl sm:text-5xl">
          Edit your <span className="italic text-primary">profile.</span>
        </h1>
        <p className="mt-3 text-muted-foreground">
          Update any field below and save. No need to go through setup again.
        </p>

        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <CandidateProfileEditForm initialData={initialData} />
        </div>
      </main>
    </CandidateShell>
  );
}
