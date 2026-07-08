import { AdminAddCandidateForm } from "@/components/admin/AdminAddCandidateForm";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";

export default async function AdminAddCandidatePage() {
  const { profile } = await requireAdmin();

  return (
    <AdminShell name={profile.full_name} activePath="/admin/candidates">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Add <span className="italic text-primary">candidate.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Manually add someone from the People Prime bench or another source.
          They will appear in the candidate registry and can be matched to roles.
        </p>

        <div className="mt-10">
          <AdminAddCandidateForm />
        </div>
      </main>
    </AdminShell>
  );
}
