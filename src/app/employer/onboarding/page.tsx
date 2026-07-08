import { EmployerCompanyForm } from "@/components/employer/EmployerCompanyForm";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function EmployerOnboardingPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("*")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (company && isCompanyProfileComplete(company)) {
    redirect("/employer");
  }

  const initialData = company
    ? {
        name: company.name,
        website: company.website ?? "",
        size: company.size ?? "",
        description: company.description ?? "",
        hqCity: company.hq_city ?? "",
        industry: company.industry ?? "",
        remoteCultureStatement: company.remote_culture_statement ?? "",
        logoUrl: company.logo_url ?? "",
      }
    : undefined;

  return (
    <EmployerShell name={profile.full_name} activePath="/employer/onboarding">
      <main className={appMainClass}>
        <div className="max-w-3xl">
        <h1 className="display-headline text-4xl">Set up your company</h1>
        <p className="mt-3 text-muted-foreground">
          US companies hiring remote tech talent. Complete your profile, then
          post your first role.
        </p>
        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <EmployerCompanyForm
            initialData={initialData}
            workEmail={profile.email}
            redirectTo="/employer/jobs/new"
          />
        </div>
        </div>
      </main>
    </EmployerShell>
  );
}
