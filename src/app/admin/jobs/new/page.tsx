import { AdminJobPostForm } from "@/components/admin/AdminJobPostForm";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";
import { getAdminClient } from "@/lib/supabase/admin";

export default async function AdminNewJobPage() {
  const { profile } = await requireAdmin();
  const supabase = await getAdminClient();
  const { data: companies } = await supabase
    .from("companies")
    .select("id, name")
    .order("name");

  return (
    <AdminShell name={profile.full_name} activePath="/admin/jobs">
      <main className={appMainClass}>
        <div className="max-w-3xl">
          <h1 className="display-headline text-4xl sm:text-5xl">
            Add <span className="italic text-primary">job.</span>
          </h1>
          <p className="mt-3 text-muted-foreground">
            Add a role for People Prime or another company. Publish immediately
            to run matching, or save it as a draft.
          </p>

          <div className="mt-10 rounded-3xl border border-border bg-card p-8">
            <AdminJobPostForm companies={companies ?? []} />
          </div>
        </div>
      </main>
    </AdminShell>
  );
}
