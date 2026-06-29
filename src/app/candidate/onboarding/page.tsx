import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { CandidateProfileForm } from "@/components/candidate/CandidateProfileForm";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";

export default async function CandidateOnboardingPage() {
  const { profile } = await requireRole("candidate");
  const supabase = await createClient();

  const { data: existing } = await supabase
    .from("candidate_profiles")
    .select("*")
    .eq("user_id", profile.id)
    .maybeSingle();

  const initialData = existing
    ? {
        headline: existing.headline ?? "",
        skills: existing.skills?.join(", ") ?? "",
        roleCategories: existing.role_categories ?? [],
        experienceLevel: existing.experience_level ?? "mid",
        salaryMin: existing.salary_min ?? undefined,
        salaryMax: existing.salary_max ?? undefined,
        workAuthorization: existing.work_authorization ?? "us_citizen",
        usState: existing.us_state ?? "Remote (US)",
        bio: existing.bio ?? "",
      }
    : undefined;

  return (
    <div className="min-h-screen bg-slate-50">
      <DashboardNav role="candidate" name={profile.full_name} />
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-3xl font-bold text-slate-900">
          Build your profile
        </h1>
        <p className="mt-3 text-slate-600">
          US remote tech roles only. Complete your profile and PrimeScale will
          match you to relevant openings.
        </p>
        <div className="mt-10 rounded-2xl border border-slate-200 bg-white p-8">
          <CandidateProfileForm initialData={initialData} />
        </div>
      </main>
    </div>
  );
}
