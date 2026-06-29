import { EmployerCompanyForm } from "@/components/employer/EmployerCompanyForm";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { requireRole } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function EmployerCompanyPage() {
  const { profile } = await requireRole("employer");
  const supabase = await createClient();

  const { data: company } = await supabase
    .from("companies")
    .select("*")
    .eq("owner_id", profile.id)
    .maybeSingle();

  if (!company) {
    redirect("/employer/onboarding");
  }

  return (
    <EmployerShell name={profile.full_name} activePath="/employer/company">
      <main className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
        <h1 className="display-headline text-4xl">Company profile</h1>
        <p className="mt-3 text-muted-foreground">
          Logo, description, HQ, industry, and remote culture — shown to matched
          candidates.
        </p>
        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <EmployerCompanyForm
            initialData={{
              name: company.name,
              website: company.website ?? "",
              size: company.size ?? "",
              description: company.description ?? "",
              hqCity: company.hq_city ?? "",
              industry: company.industry ?? "",
              remoteCultureStatement: company.remote_culture_statement ?? "",
              logoUrl: company.logo_url ?? "",
            }}
            workEmail={profile.email}
            redirectTo="/employer/company"
          />
        </div>
      </main>
    </EmployerShell>
  );
}
