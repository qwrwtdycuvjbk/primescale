import { CandidateProfileWizard } from "@/components/candidate/CandidateProfileWizard";
import { PrimeScaleLogo } from "@/components/PrimeScaleLogo";
import { requireRole } from "@/lib/auth";
import {
  isCandidateProfileComplete,
  mapCandidateRowToInput,
} from "@/lib/candidate-profile";
import { createClient } from "@/lib/supabase/server";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function CandidateOnboardingPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: existing } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("user_id", profile.id)
    .maybeSingle();

  if (isCandidateProfileComplete(existing)) {
    redirect("/candidate");
  }

  const initialData = existing
    ? mapCandidateRowToInput(existing, profile.phone)
    : { phone: profile.phone ?? "" };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/">
            <PrimeScaleLogo variant="dark" />
          </Link>
          <p className="text-sm text-muted-foreground">Step 1 of 1 — Onboarding</p>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="display-headline text-4xl sm:text-5xl">
          Build your <span className="italic text-primary">profile.</span>
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          Five steps to get matched to US remote tech roles. A resume upload is
          required on the final step.
        </p>

        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <CandidateProfileWizard
            initialData={initialData}
            redirectTo="/candidate"
          />
        </div>
      </main>
    </div>
  );
}
