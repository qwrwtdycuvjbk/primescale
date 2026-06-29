import { DashboardNav } from "@/components/dashboard/DashboardNav";
import { JobPostForm } from "@/components/employer/JobPostForm";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function NewJobPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("id")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (!company) {
    redirect("/employer/onboarding");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <DashboardNav role="employer" name={profile.full_name} />
      <main className="mx-auto max-w-2xl px-6 py-12">
        <h1 className="text-3xl font-bold text-slate-900">Post a tech role</h1>
        <p className="mt-3 text-slate-600">
          US remote tech roles only. Paste your JD or fill in details. PrimeScale
          will match qualified candidates to your role.
        </p>
        <div className="mt-10 rounded-2xl border border-slate-200 bg-white p-8">
          <JobPostForm />
        </div>
      </main>
    </div>
  );
}
