import { workAuthLabel } from "@/lib/constants";
import type { CandidateProfile, Profile } from "@/lib/types";

export type AdminCandidateRow = CandidateProfile & {
  profiles: Pick<Profile, "full_name" | "email" | "phone" | "created_at">;
  roleApplications: number;
};

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function availabilityLabel(value?: string | null) {
  switch (value) {
    case "actively_looking":
      return "Actively looking";
    case "open":
      return "Open";
    case "not_looking":
      return "Not looking";
    default:
      return "—";
  }
}

function sourceLabel(value?: string | null) {
  switch (value) {
    case "people_prime":
      return "People Prime";
    case "platform":
      return "Platform";
    default:
      return "Platform";
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

export function CandidateRegistryTable({ candidates }: { candidates: AdminCandidateRow[] }) {
  if (!candidates.length) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
        <p className="text-lg font-medium">No candidates match these filters</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Try clearing filters or check back when new candidates sign up.
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
              <th className="px-5 py-4 font-medium text-muted-foreground">Candidate</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Source</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Signed up</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Title</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Experience</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Work auth</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Availability</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Profile</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Role apps</th>
              <th className="px-5 py-4 font-medium text-muted-foreground">Contact</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {candidates.map((candidate) => {
              const profile = candidate.profiles;

              return (
                <tr key={candidate.id} className="align-top">
                  <td className="px-5 py-4">
                    <p className="font-medium">{profile.full_name || "Candidate"}</p>
                    {candidate.headline && (
                      <p className="mt-1 text-muted-foreground">{candidate.headline}</p>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        candidate.source === "people_prime"
                          ? "bg-primary/15 text-primary"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {sourceLabel(candidate.source)}
                    </span>
                  </td>
                  <td className="px-5 py-4 whitespace-nowrap text-muted-foreground">
                    {formatDate(candidate.created_at)}
                  </td>
                  <td className="px-5 py-4">{candidate.current_title ?? "—"}</td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {experienceLabel(candidate.experience_level)}
                    {candidate.years_experience != null && (
                      <span className="mt-1 block">{candidate.years_experience} yrs</span>
                    )}
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {workAuthLabel(candidate.work_authorization)}
                    {candidate.us_state && (
                      <span className="mt-1 block">{candidate.us_state}</span>
                    )}
                  </td>
                  <td className="px-5 py-4 text-muted-foreground">
                    {availabilityLabel(candidate.availability_status)}
                  </td>
                  <td className="px-5 py-4">
                    <span
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        candidate.profile_complete
                          ? "bg-primary/15 text-primary"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {candidate.profile_complete
                        ? `${candidate.profile_completeness ?? 100}%`
                        : "Incomplete"}
                    </span>
                  </td>
                  <td className="px-5 py-4 font-medium">{candidate.roleApplications}</td>
                  <td className="px-5 py-4">
                    <p className="text-muted-foreground">{profile.email}</p>
                    {(candidate.phone || profile.phone) && (
                      <p className="mt-1 text-muted-foreground">
                        {candidate.phone || profile.phone}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-3">
                      {candidate.linkedin_url && (
                        <a
                          href={candidate.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          LinkedIn
                        </a>
                      )}
                      {candidate.github_url && (
                        <a
                          href={candidate.github_url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          GitHub
                        </a>
                      )}
                      {candidate.resume_url && (
                        <a
                          href={`/api/admin/candidates/${candidate.id}/resume`}
                          target="_blank"
                          rel="noreferrer"
                          className="underline"
                        >
                          Resume
                        </a>
                      )}
                    </div>
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
