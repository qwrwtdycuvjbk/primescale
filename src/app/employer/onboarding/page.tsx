import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { CompanyOnboardingForm } from "@/components/employer/CompanyOnboardingForm";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function EmployerOnboardingPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (company) {
    redirect("/employer/jobs/new");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <DashboardNav role="employer" name={profile.full_name} />
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-3xl font-bold text-slate-900">
          Set up your company
        </h1>
        <p className="mt-3 text-slate-600">
          US companies hiring remote tech talent. Tell us about your company,
          then post your first role.
        </p>
        <div className="mt-10 rounded-2xl border border-slate-200 bg-white p-8">
          <CompanyOnboardingForm />
        </div>
      </main>
    </div>
  );
}
