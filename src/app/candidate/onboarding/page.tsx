import { CandidateProfileWizard } from "@/components/candidate/CandidateProfileWizard";
import { PeopleRemotelyLogo } from "@/components/PeopleRemotelyLogo";
import { appContainerClass, appMainClass } from "@/components/site/layout";
import { requireRole } from "@/lib/auth";
import {
  isCandidateProfileComplete,
  mapCandidateRowToInput,
} from "@/lib/candidate-profile";
import {
  MATCHING_QUEUE_COOKIE,
  isRoleCategory,
} from "@/lib/matching-seats";
import type { CandidateProfileInput } from "@/lib/types";
import { createClient } from "@/lib/supabase/server";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function CandidateOnboardingPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();
  const cookieStore = await cookies();
  const queueRaw = cookieStore.get(MATCHING_QUEUE_COOKIE)?.value;
  const queueDecoded = queueRaw ? decodeURIComponent(queueRaw) : null;
  const queueCategory = isRoleCategory(queueDecoded) ? queueDecoded : null;

  const { data: existing } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("user_id", profile.id)
    .maybeSingle();

  if (isCandidateProfileComplete(existing)) {
    redirect("/candidate");
  }

  const fromRow: Partial<CandidateProfileInput> = existing
    ? mapCandidateRowToInput(existing, profile.phone)
    : { phone: profile.phone ?? "" };
  const initialData: Partial<CandidateProfileInput> = {
    ...fromRow,
    roleCategories:
      fromRow.roleCategories && fromRow.roleCategories.length > 0
        ? fromRow.roleCategories
        : queueCategory
          ? [queueCategory]
          : fromRow.roleCategories ?? [],
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className={`${appContainerClass} flex items-center justify-between py-4`}>
          <Link href="/">
            <PeopleRemotelyLogo variant="dark" />
          </Link>
          <p className="text-base text-muted-foreground">5-step onboarding</p>
        </div>
      </header>

      <main className={appMainClass}>
        <div className="max-w-3xl">
        <h1 className="display-headline text-4xl sm:text-5xl">
          Join the matching{" "}
          <span className="italic text-foreground">queue.</span>
        </h1>
        <p className="mt-4 max-w-xl text-lg text-muted-foreground">
          {queueCategory
            ? `You’re joining the ${queueCategory} queue. Five steps to finish your profile. Resume upload required on the final step.`
            : "Five steps to join a matching queue for remote tech seats. A resume upload is required on the final step."}
        </p>

        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <CandidateProfileWizard
            initialData={initialData}
            redirectTo="/candidate"
          />
        </div>
        </div>
      </main>
    </div>
  );
}
