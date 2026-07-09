import { AdminCandidateCsvImport } from "@/components/admin/AdminCandidateCsvImport";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin } from "@/lib/auth";

export default async function AdminCandidateImportPage() {
  const { profile } = await requireAdmin();

  return (
    <AdminShell name={profile.full_name} activePath="/admin/candidates">
      <main className={appMainClass}>
        <h1 className="display-headline text-4xl sm:text-5xl">
          Import <span className="italic text-primary">candidates.</span>
        </h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Bulk-add People Prime bench talent from Excel. Download the template,
          fill the Candidates sheet using the Valid values sheet, then upload.
        </p>

        <div className="mt-10">
          <AdminCandidateCsvImport />
        </div>
      </main>
    </AdminShell>
  );
}
