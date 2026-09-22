import Link from "next/link";
import {
  ArrowLeft,
  Briefcase,
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  ExternalLink,
  FileText,
  Globe,
  Mail,
  MapPin,
  Phone,
  Shield,
  Sparkles,
  User,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { candidatesApi, matchingApi } from "@/lib/api";
import { workAuthLabel } from "@/lib/constants";
import { CandidateAccountActionButtons } from "@/components/admin/CandidateAccountActionButtons";
import type { DjangoCandidateProfile } from "@/lib/api/candidates";
import type { DjangoMatch } from "@/lib/api/matching";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function availabilityBadge(status?: string | null) {
  switch (status) {
    case "actively_looking":
      return { label: "Actively Looking", bg: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20" };
    case "open":
      return { label: "Open to Offers", bg: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20" };
    case "not_looking":
      return { label: "Not Looking", bg: "bg-muted text-muted-foreground border-border" };
    default:
      return { label: status || "Unknown", bg: "bg-muted text-muted-foreground border-border" };
  }
}

function formatSalary(min?: number | null, max?: number | null) {
  if (!min && !max) return "Not specified";
  if (min && max) return `$${min.toLocaleString()} – $${max.toLocaleString()} / year`;
  if (min) return `From $${min.toLocaleString()} / year`;
  return `Up to $${max?.toLocaleString()} / year`;
}

export default async function AdminCandidateDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { profile: adminProfile } = await requireAdmin();
  const token = await getAccessToken();

  let candidate: DjangoCandidateProfile | null = null;
  let matches: DjangoMatch[] = [];
  let errorState: string | null = null;

  try {
    const candidateData = await candidatesApi.getAdminCandidate(id, { token });
    if (candidateData && candidateData.id) {
      candidate = candidateData;
    }
  } catch (err: any) {
    console.error("Failed to load candidate profile:", err);
    errorState = err?.message || "Candidate not found";
  }

  // Load matches/applications for this candidate if available
  if (candidate) {
    try {
      const allMatches = await matchingApi.listMatches(undefined, { token });
      if (allMatches && Array.isArray(allMatches)) {
        matches = allMatches.filter(
          (m) =>
            m.candidate_profile_id === candidate?.id ||
            m.candidate_profile?.id === candidate?.id ||
            m.candidate_profiles?.id === candidate?.id
        );
      }
    } catch (err) {
      console.error("Failed to load candidate matches:", err);
    }
  }

  if (!candidate || errorState) {
    return (
      <AdminShell name={adminProfile.full_name} activePath="/admin/candidates">
        <main className={appMainClass}>
          <Link
            href="/admin/candidates"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Candidates
          </Link>

          <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center max-w-xl mx-auto">
            <User className="mx-auto h-12 w-12 text-muted-foreground/40" />
            <h2 className="mt-4 text-xl font-semibold">Candidate Not Found</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {errorState || "The requested candidate profile could not be loaded or does not exist."}
            </p>
            <div className="mt-6">
              <Link
                href="/admin/candidates"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
              >
                Return to Candidate Registry
              </Link>
            </div>
          </div>
        </main>
      </AdminShell>
    );
  }

  const avail = availabilityBadge(candidate.availability_status);
  const rawFullName =
    candidate.user_full_name ||
    candidate.full_name ||
    candidate.name ||
    candidate.user?.full_name ||
    "";
  const fullName = rawFullName.trim() || "Candidate Profile";

  const rawEmail =
    candidate.user_email ||
    candidate.email ||
    candidate.user?.email ||
    "";
  const email = rawEmail.trim() || "No email";

  const phone = candidate.phone || "No phone";
  const skillsList = Array.isArray(candidate.skills) ? candidate.skills : [];
  const roleCats = Array.isArray(candidate.role_categories) ? candidate.role_categories : [];
  const isActive =
    candidate.user_is_active !== undefined
      ? candidate.user_is_active
      : candidate.is_active !== undefined
        ? candidate.is_active
        : (candidate.user?.is_active ?? true);

  return (
    <AdminShell name={adminProfile.full_name} activePath="/admin/candidates">
      <main className={appMainClass}>
        {/* Back Link */}
        <div className="mb-6 flex items-center justify-between">
          <Link
            href="/admin/candidates"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Candidates
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Candidate ID:</span>
            <code className="rounded bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground">
              {candidate.id}
            </code>
          </div>
        </div>

        {/* Header Profile Card */}
        <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary font-bold text-2xl">
                {fullName.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                    {fullName}
                  </h1>
                  {/* Account Status Badge */}
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold ${
                      isActive
                        ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                        : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${isActive ? "bg-emerald-500" : "bg-red-500"}`} />
                    {isActive ? "Active Account" : "Inactive Account"}
                  </span>
                  <span className={`rounded-full border px-3 py-0.5 text-xs font-medium ${avail.bg}`}>
                    {avail.label}
                  </span>
                  <span className="rounded-full bg-muted px-3 py-0.5 text-xs font-medium text-muted-foreground">
                    {candidate.source === "people_prime" ? "People Prime Bench" : "Direct Platform"}
                  </span>
                </div>

                {candidate.headline && (
                  <p className="mt-1 text-base text-muted-foreground font-medium">
                    {candidate.headline}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Mail className="h-4 w-4 text-muted-foreground/70" />
                    {email}
                  </span>
                  {phone && phone !== "No phone" && (
                    <span className="inline-flex items-center gap-1.5">
                      <Phone className="h-4 w-4 text-muted-foreground/70" />
                      {phone}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1.5">
                    <Calendar className="h-4 w-4 text-muted-foreground/70" />
                    Joined {formatDate(candidate.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Actions Header: Resume & Account Action Controls */}
            <div className="flex flex-wrap items-center gap-3 lg:self-start">
              <CandidateAccountActionButtons
                candidateId={candidate.id}
                candidateName={fullName}
                candidateEmail={email}
                isActive={isActive}
                compact={false}
              />

              {candidate.resume_url ? (
                <a
                  href={`/api/admin/candidates/${candidate.id}/resume`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground shadow-sm transition hover:opacity-90"
                >
                  <FileText className="h-4 w-4" />
                  View Resume
                  <Download className="h-3.5 w-3.5" />
                </a>
              ) : (
                <span className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
                  <FileText className="h-3.5 w-3.5" />
                  No resume uploaded
                </span>
              )}
            </div>
          </div>

          {/* Profile Completeness Bar */}
          <div className="mt-6 pt-6 border-t border-border">
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-medium text-foreground">Profile Completeness</span>
              <span className="font-semibold text-foreground">
                {candidate.profile_completeness ?? (candidate.profile_complete ? 100 : 0)}%
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{
                  width: `${Math.min(100, candidate.profile_completeness ?? (candidate.profile_complete ? 100 : 0))}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Content Grid */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left 2 Columns: Professional Information & Details */}
          <div className="lg:col-span-2 space-y-8">
            {/* Bio Section */}
            {candidate.bio && (
              <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
                <h2 className="text-lg font-semibold text-foreground mb-4">About / Bio</h2>
                <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-line">
                  {candidate.bio}
                </p>
              </div>
            )}

            {/* Professional Info */}
            <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
              <h2 className="text-lg font-semibold text-foreground mb-6">Professional Profile</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-sm">
                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Current Title</span>
                  <p className="mt-1 font-semibold text-foreground">
                    {candidate.current_title || "Not specified"}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Experience Level</span>
                  <p className="mt-1 font-semibold text-foreground capitalize">
                    {candidate.experience_level ? `${candidate.experience_level} Level` : "Not specified"}
                    {candidate.years_experience ? ` (${candidate.years_experience} years)` : ""}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Salary Expectations</span>
                  <p className="mt-1 font-semibold text-foreground">
                    {formatSalary(candidate.salary_min, candidate.salary_max)}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Work Authorization</span>
                  <p className="mt-1 font-semibold text-foreground">
                    {workAuthLabel(candidate.work_authorization)}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Location / State</span>
                  <p className="mt-1 font-semibold text-foreground">
                    {candidate.us_state || "Any US Location"}
                  </p>
                </div>

                <div>
                  <span className="text-xs font-medium text-muted-foreground block">Preferred Work Type</span>
                  <p className="mt-1 font-semibold text-foreground capitalize">
                    {candidate.preferred_work_type || candidate.remote_preference || "Remote"}
                  </p>
                </div>
              </div>

              {/* Skills Tags */}
              <div className="mt-6 pt-6 border-t border-border">
                <span className="text-xs font-medium text-muted-foreground block mb-3">
                  Technical & Professional Skills ({skillsList.length})
                </span>
                {skillsList.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {skillsList.map((skill, i) => (
                      <span
                        key={i}
                        className="rounded-xl border border-border bg-muted/50 px-3 py-1 text-xs font-medium text-foreground"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No skills specified.</p>
                )}
              </div>

              {/* Role Categories */}
              {roleCats.length > 0 && (
                <div className="mt-6 pt-6 border-t border-border">
                  <span className="text-xs font-medium text-muted-foreground block mb-3">
                    Target Role Categories
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {roleCats.map((role, i) => (
                      <span
                        key={i}
                        className="rounded-full bg-primary/10 text-primary px-3 py-1 text-xs font-medium"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Platform Matches & Applications Section */}
            <div className="rounded-3xl border border-border bg-card p-6 sm:p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-foreground">
                  Recorded Matches & Opportunities
                </h2>
                <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {matches.length} Total
                </span>
              </div>

              {matches.length > 0 ? (
                <div className="divide-y divide-border">
                  {matches.map((match) => {
                    const jobTitle = match.job?.title || match.jobs?.title || match.job_title || "Job Opportunity";
                    const company = match.job?.companies?.name || match.job?.company_name || match.job?.company?.name || "Company";

                    return (
                      <div key={match.id} className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                          <p className="font-medium text-foreground text-sm">{jobTitle}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{company}</p>
                          {match.match_reason && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-1 italic">
                              "{match.match_reason}"
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className="rounded-full bg-primary/10 text-primary px-2.5 py-1 text-xs font-bold">
                            {match.match_score}% fit
                          </span>
                          <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground capitalize">
                            {match.status.replace("_", " ")}
                          </span>
                          <Link
                            href="/admin/matches"
                            className="text-xs font-medium text-foreground hover:text-primary underline"
                          >
                            Review
                          </Link>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-muted-foreground">
                  <Sparkles className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                  No active matches recorded for this candidate yet.
                </div>
              )}
            </div>
          </div>

          {/* Right Column: External Links, Resume, Metadata */}
          <div className="space-y-8">
            {/* External Links */}
            <div className="rounded-3xl border border-border bg-card p-6">
              <h3 className="text-base font-semibold text-foreground mb-4">Profiles & Links</h3>
              <div className="space-y-3 text-sm">
                {candidate.linkedin_url ? (
                  <a
                    href={candidate.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border border-border p-3 transition hover:bg-muted/40"
                  >
                    <span className="font-medium">LinkedIn Profile</span>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </a>
                ) : (
                  <div className="flex items-center justify-between rounded-xl border border-border/60 bg-muted/20 p-3 text-muted-foreground text-xs">
                    <span>LinkedIn</span>
                    <span>Not provided</span>
                  </div>
                )}

                {candidate.github_url ? (
                  <a
                    href={candidate.github_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border border-border p-3 transition hover:bg-muted/40"
                  >
                    <span className="font-medium">GitHub Profile</span>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </a>
                ) : (
                  <div className="flex items-center justify-between rounded-xl border border-border/60 bg-muted/20 p-3 text-muted-foreground text-xs">
                    <span>GitHub</span>
                    <span>Not provided</span>
                  </div>
                )}

                {candidate.portfolio_url ? (
                  <a
                    href={candidate.portfolio_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between rounded-xl border border-border p-3 transition hover:bg-muted/40"
                  >
                    <span className="font-medium">Portfolio / Website</span>
                    <ExternalLink className="h-4 w-4 text-muted-foreground" />
                  </a>
                ) : (
                  <div className="flex items-center justify-between rounded-xl border border-border/60 bg-muted/20 p-3 text-muted-foreground text-xs">
                    <span>Portfolio</span>
                    <span>Not provided</span>
                  </div>
                )}
              </div>
            </div>

            {/* Resume Card */}
            <div className="rounded-3xl border border-border bg-card p-6">
              <h3 className="text-base font-semibold text-foreground mb-4">Resume Document</h3>
              {candidate.resume_url ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 rounded-2xl bg-muted/50 p-4 border border-border">
                    <FileText className="h-8 w-8 text-primary shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-foreground truncate">
                        Candidate_Resume.pdf
                      </p>
                      <p className="text-xs text-muted-foreground">Stored securely in private S3</p>
                    </div>
                  </div>

                  <a
                    href={`/api/admin/candidates/${candidate.id}/resume`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex w-full items-center justify-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition hover:opacity-90 shadow-sm"
                  >
                    <Download className="h-4 w-4" />
                    Download Resume
                  </a>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
                  <FileText className="mx-auto h-8 w-8 text-muted-foreground/30 mb-2" />
                  No resume document attached to this candidate account.
                </div>
              )}
            </div>

            {/* Admin Actions */}
            <div className="rounded-3xl border border-border bg-card p-6">
              <h3 className="text-base font-semibold text-foreground mb-4">Admin Shortcuts</h3>
              <div className="space-y-2">
                <Link
                  href="/admin/matches"
                  className="flex w-full items-center justify-between rounded-xl border border-border p-3 text-xs font-medium hover:bg-muted/40 transition"
                >
                  <span>View Match Review Queue</span>
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </Link>
                <Link
                  href={`/admin/applications?q=${encodeURIComponent(fullName)}`}
                  className="flex w-full items-center justify-between rounded-xl border border-border p-3 text-xs font-medium hover:bg-muted/40 transition"
                >
                  <span>Filter Candidate Applications</span>
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </main>
    </AdminShell>
  );
}