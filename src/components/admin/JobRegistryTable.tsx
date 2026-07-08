import type { Company, Job, JobStatus, Profile } from "@/lib/types";

export type AdminJobRow = Omit<Job, "companies"> & {
  companies: Pick<Company, "name" | "website"> | null;
  profiles: Pick<Profile, "full_name" | "email" | "phone"> | null;
  matchCount: number;
  releasedMatchCount: number;
};

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function statusLabel(status: JobStatus) {
  switch (status) {
    case "active":
      return "Active";
    case "draft":
      return "Draft";
    case "paused":
      return "Paused";
    case "closed":
      return "Closed";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

function statusClass(status: JobStatus) {
  switch (status) {
    case "active":
      return "bg-primary/15 text-primary";
    case "draft":
      return "bg-muted text-muted-foreground";
    case "paused":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
    case "closed":
    case "archived":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function experienceLabel(value?: string | null) {
  switch (value) {
    case "junior":
      return "Junior";
    case "mid":
      return "Mid";
    case "senior":
      return "Senior";
    case "lead":
      return "Lead";
    default:
      return "—";
  }
}

function roleTypeLabel(value?: string | null) {
  switch (value) {
    case "contract":
      return "Contract";
    case "c2h":
      return "C2H";
    case "full-time":
      return "Full-time";
    default:
      return "—";
  }
}

export function JobRegistryTable({ jobs }: { jobs: AdminJobRow[] }) {
  if (!jobs.length) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
        <p className="text-lg font-medium">No roles match these filters</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Try clearing filters or check back when employers post new roles.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              <th className="px-5 py-4 font-medium text-muted-foreground">Role</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Company</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Posted</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Status</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Level / type</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Salary</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Matches</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Posted by</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.map((job) => {
              const company = job.companies;
              const employer = job.profiles;

              return (
                <tr key={job.id} className="align-top">
                  <td className="px-5 py-4">
                    <p className="font-medium">{job.title}</p>
                    {job.tech_stack?.length > 0 && (
                      <p className="mt-1 text-muted-foreground">
                        {job.tech_stack.slice(0, 4).join(", ")}
                        {job.tech_stack.length > 4 ? "…" : ""}
                      </p>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <p className="font-medium">{company?.name ?? "—"}</p>
                    {company?.website && (
                      <a
                        href={company.website.startsWith("http") ? company.website : `https://${company.website}`}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 block text-muted-foreground underline"
                      >
                        Website
                      </a>
                    )}
                  </td>
                  <td className="px-5 py-4 whitespace-nowrap text-muted-foreground">
                    {formatDate(job.created_at)}
                    {job.expires_at && (
                      <span className="mt-1 block text-xs">
                        Expires {formatDate(job.expires_at)}
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${statusClass(job.status)}`}
                    >
                      {statusLabel(job.status)}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {experienceLabel(job.experience_level)}
                    <span className="mt-1 block">{roleTypeLabel(job.role_type)}</span>
                    <span className="mt-1 block capitalize">{job.work_type}</span>
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {job.salary_range ?? "—"}
                  </td>
                  <td className="px-5 py-4">
                    <p className="font-medium">{job.matchCount}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {job.releasedMatchCount} released
                    </p>
                  </td>
                  <td className="px-5 py-4">
                    <p className="font-medium">{employer?.full_name ?? "—"}</p>
                    {employer?.email && (
                      <p className="mt-1 text-muted-foreground">{employer.email}</p>
                    )}
                    {employer?.phone && (
                      <p className="mt-1 text-muted-foreground">{employer.phone}</p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
