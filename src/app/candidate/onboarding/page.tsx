import { CandidateProfileWizard } from "@/components/candidate/CandidateProfileWizard";
import { PeopleRemotelyLogo } from "@/components/PeopleRemotelyLogo";
import { appContainerClass, appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import {
  isCandidateProfileComplete,
  mapCandidateRowToInput,
} from "@/lib/candidate-profile";
import {
  MATCHING_QUEUE_COOKIE,
  isRoleCategory,
} from "@/lib/matching-seats";
import type { CandidateProfileInput } from "@/lib/types";
import { candidatesApi } from "@/lib/api";
import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function CandidateOnboardingPage() {
  const { profile } = await requireRole("candidate");
  const token = await getAccessToken();
  const cookieStore = await cookies();
  const queueRaw = cookieStore.get(MATCHING_QUEUE_COOKIE)?.value;
  const queueDecoded = queueRaw ? decodeURIComponent(queueRaw) : null;
  const queueCategory = isRoleCategory(queueDecoded) ? queueDecoded : null;

  let existing = null;
  try {
    existing = await candidatesApi.getMyProfile({ token });
  } catch (err) {
    console.error("Failed to load candidate profile from Django:", err);
  }

  if (existing && isCandidateProfileComplete(existing)) {
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

  async function signOut() {
    "use server";
    const { clearDjangoAuthCookies } = await import("@/lib/auth-actions");
    await clearDjangoAuthCookies();
    redirect("/auth/login");
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className={`${appContainerClass} flex items-center justify-between py-4`}>
          <Link href="/">
            <PeopleRemotelyLogo variant="dark" />
          </Link>
          <div className="flex items-center gap-6">
            <p className="text-sm text-muted-foreground hidden sm:block">5-step onboarding</p>
            <form action={signOut}>
              <button
                type="submit"
                className="text-sm font-medium text-muted-foreground transition hover:text-foreground"
              >
                Sign out
              </button>
            </form>
          </div>
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
