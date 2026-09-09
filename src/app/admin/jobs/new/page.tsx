import { AdminJobPostForm } from "@/components/admin/AdminJobPostForm";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { companiesApi } from "@/lib/api";

export default async function AdminNewJobPage() {
  const { profile } = await requireAdmin();
  const token = await getAccessToken();

  let companies: { id: string; name: string }[] = [];

  try {
    const djangoCompanies = await companiesApi.listCompanies({ token });
    if (Array.isArray(djangoCompanies)) {
      companies = djangoCompanies.map((c) => ({ id: c.id, name: c.name }));
    }
  } catch (err) {
    console.error("Failed to load companies from Django:", err);
  }

  return (
    <AdminShell name={profile.full_name} activePath="/admin/jobs">
      <main className={appMainClass}>
        <div className="max-w-3xl">
          <h1 className="display-headline text-4xl sm:text-5xl">
            Add <span className="italic text-foreground">job.</span>
          </h1>
          <p className="mt-3 text-muted-foreground">
            Add a role for People Prime or another company. Publish immediately
            to run matching, or save it as a draft.
          </p>

          <div className="mt-10 rounded-3xl border border-border bg-card p-8">
            <AdminJobPostForm companies={companies} />
          </div>
        </div>
      </main>
    </AdminShell>
  );
}
