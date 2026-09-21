import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  Briefcase,
  CheckCircle2,
  ExternalLink,
  FileText,
  LogOut,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { CandidateShell } from "@/components/candidate/CandidateShell";
import { appMainClass } from "@/components/site/layout";
import { requireRole, getAccessToken } from "@/lib/auth";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import { candidatesApi, matchingApi, applicationsApi } from "@/lib/api";
import { clearDjangoAuthCookies } from "@/lib/auth-actions";
import { redirect } from "next/navigation";

function formatAppStatus(status?: string): { label: string; className: string } {
  switch (status) {
    case "candidate_interested":
      return {
        label: "Applied",
        className: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
      };
    case "employer_shortlisted":
      return {
        label: "Shortlisted",
        className: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
      };
    case "mutual_fit":
      return {
        label: "Mutual Fit",
        className: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
      };
    case "rejected":
      return {
        label: "Not Selected",
        className: "bg-muted text-muted-foreground border-border",
      };
    default:
      return {
        label: status?.replace(/_/g, " ") || "Submitted",
        className: "bg-muted text-muted-foreground border-border",
      };
  }
}

function formatApplicationDate(dateStr?: string): string {
  if (!dateStr) return "Recently";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "Recently";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(d);
  } catch {
    return "Recently";
  }
}

export default async function CandidateDashboardPage() {
  const { profile } = await requireRole("candidate");
  const token = await getAccessToken();

  async function handleSignOut() {
    "use server";
    await clearDjangoAuthCookies();
    redirect("/auth/candidate/login");
  }

  let candidateProfile = null;
  try {
    candidateProfile = await candidatesApi.getMyProfile({ token });
  } catch (err) {
    console.error("Failed to load candidate profile from Django:", err);
  }

  const isComplete = Boolean(
    candidateProfile && isCandidateProfileComplete(candidateProfile),
  );

  let matches: any[] = [];
  let matchCount = 0;
  let applications: any[] = [];

  if (isComplete) {
    try {
      const djangoMatches = await matchingApi.listMatches({}, { token });
      if (djangoMatches && Array.isArray(djangoMatches)) {
        // Enforce match_score > 60 (60 is excluded, 61+ included)
        const qualifiedMatches = djangoMatches.filter(
          (m: any) => typeof m.match_score === "number" && m.match_score > 60,
        );
        matchCount = qualifiedMatches.length;
        matches = qualifiedMatches.slice(0, 4);
      }
    } catch (err) {
      console.error("Failed to load candidate matches from Django:", err);
    }
  }

  try {
    const djangoApps = await applicationsApi.listApplications({}, { token });
    if (djangoApps && Array.isArray(djangoApps)) {
      applications = djangoApps;
    }
  } catch (err) {
    console.error("Failed to load candidate applications from Django:", err);
  }

  const firstName = profile.full_name?.trim().split(" ")[0] || "there";

  return (
    <CandidateShell name={profile.full_name} activePath="/candidate">
      <main className={appMainClass}>
        {/* Top Header */}
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="display-headline text-4xl sm:text-5xl">
              Welcome back,{" "}
              <span className="italic text-foreground">{firstName}.</span>
            </h1>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Your personal dashboard for profile status, remote job matches,
              and application tracking.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href={isComplete ? "/candidate/profile" : "/candidate/onboarding"}
              className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5"
            >
              {isComplete ? "Edit Profile" : "Complete Profile"}
              <ArrowRight className="h-4 w-4" />
            </Link>
            <form action={handleSignOut}>
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2.5 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                <LogOut className="h-4 w-4" />
                Sign Out
              </button>
            </form>
          </div>
        </div>

        {/* Section 1: Incomplete Profile Banner Alert */}
        {!isComplete && (
          <div className="mt-8 rounded-3xl border border-amber-500/30 bg-amber-500/10 p-6 sm:p-8">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">
                    Please complete your profile
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
                    To unlock personalized remote job matches and join candidate
                    shortlists, complete your required profile details and upload
                    your resume (mandatory).
                  </p>
                </div>
              </div>
              <Link
                href="/candidate/onboarding"
                className="shrink-0 inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
              >
                <span>Complete Profile</span>
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        )}

        {/* Summary Metric Cards */}
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Sparkles className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">{matchCount}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Qualified Matches (&gt;60%)
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <Briefcase className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">
              {applications.length}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">Jobs Applied</p>
          </div>

          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted text-foreground">
              <FileText className="h-5 w-5" />
            </div>
            <p className="display-headline mt-6 text-4xl">
              {isComplete ? "100%" : `${candidateProfile?.profile_completeness ?? 0}%`}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {isComplete ? "Profile Complete" : "Profile Incomplete"}
            </p>
          </div>
        </div>

        {/* Main Grid: Section 1 (Your Profile) & Section 2 (Job Matches) */}
        <section className="mt-10 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          {/* Section 2: Job Matches */}
          <div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="display-headline text-2xl">Job Matches</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Roles matching your skills &amp; experience (Score &gt; 60%)
                </p>
              </div>
              {isComplete && matches.length > 0 && (
                <Link
                  href="/candidate/matches"
                  className="text-sm font-semibold text-primary hover:underline"
                >
                  View all ({matchCount})
                </Link>
              )}
            </div>

            <div className="mt-6 space-y-4">
              {!isComplete ? (
                <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold text-foreground">
                    Complete your profile to see personalized job matches.
                  </h3>
                  <p className="mt-2 text-xs text-muted-foreground max-w-md mx-auto">
                    Your matching queue activates as soon as your candidate
                    profile and required resume are saved.
                  </p>
                  <div className="mt-6">
                    <Link
                      href="/candidate/onboarding"
                      className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground"
                    >
                      Complete Profile Now
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              ) : matches.length > 0 ? (
                matches.map((match: any) => {
                  const job = match.job || match.jobs;
                  const companyName =
                    job?.company_name || job?.companies?.name || "Company";
                  const score = match.match_score ?? 0;
                  const targetJobId = job?.id || match.job_id;

                  return (
                    <article
                      key={match.id}
                      className="rounded-3xl border border-border bg-card p-6 transition-all hover:border-primary/40 hover:shadow-sm"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2.5 py-0.5 text-xs font-mono font-bold text-primary">
                              {score}% match
                            </span>
                            {job?.work_type && (
                              <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium capitalize text-muted-foreground">
                                {job.work_type}
                              </span>
                            )}
                          </div>
                          <h3 className="text-xl font-bold mt-2 text-foreground">
                            {job?.title || "Remote Role"}
                          </h3>
                          <p className="text-xs font-medium text-muted-foreground mt-0.5">
                            {companyName}
                            {job?.role_type ? ` · ${job.role_type}` : ""}
                          </p>
                        </div>

                        {targetJobId && (
                          <Link
                            href={`/jobs/external/${targetJobId}`}
                            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
                          >
                            <span>View Job</span>
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                        )}
                      </div>

                      {match.match_reason && (
                        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                          {match.match_reason}
                        </p>
                      )}

                      {job?.tech_stack && job.tech_stack.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-1.5">
                          {job.tech_stack.slice(0, 5).map((skill: string) => (
                            <span
                              key={skill}
                              className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] font-mono text-muted-foreground"
                            >
                              {skill}
                            </span>
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })
              ) : (
                <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
                  <p className="text-base font-semibold text-foreground">
                    No matching jobs found yet.
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground max-w-md mx-auto">
                    We scan active roles against your profile. New roles
                    qualifying with &gt;60% match score will appear here.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Section 1: Your Profile Aside Card */}
          <aside className="rounded-3xl border border-border bg-card p-6 sm:p-8">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs uppercase tracking-widest text-foreground">
                Your Profile
              </p>
              {isComplete ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Profile Complete
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-3.5 w-3.5" />
                  Incomplete
                </span>
              )}
            </div>

            <h3 className="display-headline mt-4 text-2xl sm:text-3xl">
              {candidateProfile?.headline || profile.full_name || "Candidate Profile"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {candidateProfile?.current_title || "Remote Professional"}
              {candidateProfile?.us_state ? ` · ${candidateProfile.us_state}` : ""}
            </p>

            {candidateProfile?.skills && candidateProfile.skills.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-1.5">
                {candidateProfile.skills.slice(0, 8).map((skill: string) => (
                  <span
                    key={skill}
                    className="rounded-full border border-border bg-background px-3 py-1 text-xs"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            )}

            <dl className="mt-6 space-y-3.5 border-t border-border pt-6 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Availability</dt>
                <dd className="font-medium capitalize text-foreground">
                  {candidateProfile?.availability_status?.replace(/_/g, " ") ||
                    "Actively Looking"}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Preferred Work</dt>
                <dd className="font-medium capitalize text-foreground">
                  {candidateProfile?.preferred_work_type || "Remote"}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">Resume Status</dt>
                <dd className="font-medium">
                  {candidateProfile?.resume_url ? (
                    <span className="text-emerald-600 dark:text-emerald-400">
                      Uploaded &amp; Verified
                    </span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400">
                      Missing (Required)
                    </span>
                  )}
                </dd>
              </div>
            </dl>

            <Link
              href={isComplete ? "/candidate/profile" : "/candidate/onboarding"}
              className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-full border border-border bg-background py-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
            >
              {isComplete ? "Edit Profile" : "Complete Profile"}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </aside>
        </section>

        {/* Section 3: Job Application Tracker */}
        <section className="mt-12">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="display-headline text-2xl">
                Job Application Tracker
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Track status and history for your candidate applications.
              </p>
            </div>
            <span className="text-xs font-mono font-semibold rounded-full border border-border px-3 py-1 bg-card text-muted-foreground">
              {applications.length} Applied
            </span>
          </div>

          <div className="mt-6">
            {applications.length > 0 ? (
              <div className="divide-y divide-border rounded-3xl border border-border bg-card overflow-hidden">
                {applications.map((app: any) => {
                  const job = app.job || app.jobs;
                  const companyName =
                    job?.company_name || job?.companies?.name || "Company";
                  const statusInfo = formatAppStatus(app.status);
                  const appliedDate = formatApplicationDate(
                    app.applied_at || app.updated_at || app.created_at,
                  );
                  const targetJobId = job?.id || app.job_id;

                  return (
                    <div
                      key={app.id}
                      className="p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-colors hover:bg-muted/30"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2.5">
                          <h3 className="text-base font-bold text-foreground">
                            {job?.title || "Software Engineering Role"}
                          </h3>
                          <span
                            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusInfo.className}`}
                          >
                            {statusInfo.label}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          <span className="font-medium text-foreground">
                            {companyName}
                          </span>
                          {job?.work_type ? ` · ${job.work_type}` : ""}
                          <span> · Applied {appliedDate}</span>
                        </p>
                      </div>

                      {targetJobId && (
                        <div className="shrink-0">
                          <Link
                            href={`/jobs/external/${targetJobId}`}
                            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
                          >
                            <span>View Job</span>
                            <ExternalLink className="h-3.5 w-3.5" />
                          </Link>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-3xl border border-dashed border-border bg-card p-10 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
                  <Briefcase className="h-6 w-6" />
                </div>
                <h3 className="mt-4 text-base font-semibold text-foreground">
                  You haven&apos;t applied to any jobs yet.
                </h3>
                <p className="mt-2 text-xs text-muted-foreground max-w-md mx-auto">
                  When you apply to matched opportunities, you can track their
                  progress and review submission dates here.
                </p>
              </div>
            )}
          </div>
        </section>
      </main>
    </CandidateShell>
  );
}

