import { JobPostForm } from "@/components/employer/JobPostForm";
import { EmployerShell } from "@/components/employer/EmployerShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCompanyProfileComplete } from "@/lib/employer";
import { companiesApi } from "@/lib/api";
import { redirect } from "next/navigation";

export default async function NewJobPage() {
  const { profile } = await requireRole("employer");
  const token = await getAccessToken();

  let company = null;
  try {
    company = await companiesApi.getMyCompany({ token });
  } catch (err) {
    console.error("Failed to load company from Django:", err);
  }

  if (!company || !isCompanyProfileComplete(company)) {
    redirect("/employer/onboarding");
  }

  return (
    <EmployerShell name={profile.full_name} activePath="/employer/jobs">
      <main className={appMainClass}>
        <div className="max-w-3xl">
        <h1 className="display-headline text-4xl">Post a tech role</h1>
        <p className="mt-3 text-muted-foreground">
          Paste your JD or fill in details — salary
          range is required. Preview before publishing.
        </p>
        <div className="mt-10 rounded-3xl border border-border bg-card p-8">
          <JobPostForm companyName={company.name} />
        </div>
        </div>
      </main>
    </EmployerShell>
  );
}
