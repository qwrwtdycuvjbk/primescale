import { Shield } from "lucide-react";

export function AdminCandidateActions() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-2 text-xs font-medium text-muted-foreground">
        <Shield className="h-3.5 w-3.5 text-primary" />
        Read-Only Candidate Registry
      </span>
    </div>
  );
}
