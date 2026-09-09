import { EmployerCompanyForm } from "@/components/employer/EmployerCompanyForm";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { companiesApi } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function EmployerOnboardingPage() {
  const { profile } = await requireRole("employer");
  const token = await getAccessToken();

  let company = null;
  try {
    company = await companiesApi.getMyCompany({ token });
  } catch (err) {
    console.error("Failed to load company from Django:", err);
  }

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
          Companies hiring remote tech talent worldwide. Complete your profile, then
          post your first role.
        </p>
        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <EmployerCompanyForm
            initialData={initialData}
            workEmail={profile.email}
            redirectTo="/employer"
          />
        </div>
        </div>
      </main>
    </EmployerShell>
  );
}
