import Link from "next/link";
import { ArrowRight, FileSpreadsheet, UserPlus } from "lucide-react";

export function AdminCandidateActions() {
  return (
    <div className="flex flex-wrap gap-3">
      <Link
        href="/admin/candidates/new"
        className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
      >
        <UserPlus className="h-4 w-4" />
        Add candidate
        <ArrowRight className="h-4 w-4" />
      </Link>
      <Link
        href="/admin/candidates/import"
        className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-5 py-2.5 text-sm font-semibold transition-colors hover:bg-muted"
      >
        <FileSpreadsheet className="h-4 w-4" />
        Import Excel
      </Link>
    </div>
  );
}
