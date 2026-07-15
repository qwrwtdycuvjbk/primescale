import { AdminJobLeadsClient } from "@/components/admin/AdminJobLeadsClient";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";

export default async function AdminJobLeadsPage() {
  const { profile } = await requireAdmin();

  return (
    <AdminShell name={profile.full_name} activePath="/admin/job-leads">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Job <span className="italic text-primary">leads.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Pull fresh remote tech roles from OpenWeb Ninja. Use these to outreach
          companies and match against the People Prime bench, then invite them to
          post on PrimeScale.
        </p>

        <div className="mt-10">
          <AdminJobLeadsClient />
        </div>
      </main>
    </AdminShell>
  );
}
