"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Building2,
  MapPin,
  Calendar,
  ChevronLeft,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Send,
  Loader2,
  Globe,
} from "lucide-react";
import { SiteHeader } from "@/components/site/site-header";
import { SiteFooter } from "@/components/site/site-footer";
import {
  jobsApi,
  EmployerPublicJob,
  djangoAuth,
  candidatesApi,
  applicationsApi,
} from "@/lib/api";
import { isCandidateProfileComplete } from "@/lib/candidate-profile";
import type { Profile } from "@/lib/types";

function formatDate(dateStr?: string | null): string | null {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return null;
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(d);
  } catch {
    return null;
  }
}

function formatRoleType(roleType?: string): string {
  if (!roleType) return "Full-time";
  if (roleType.toLowerCase() === "c2h") return "Contract-to-Hire";
  if (roleType.toLowerCase() === "full-time") return "Full-time";
  if (roleType.toLowerCase() === "contract") return "Contract";
  return roleType.charAt(0).toUpperCase() + roleType.slice(1);
}

function formatExperienceLevel(level?: string): string {
  if (!level) return "Mid-level";
  if (level.toLowerCase() === "lead") return "Lead / Staff";
  return level.charAt(0).toUpperCase() + level.slice(1);
}

export default function EmployerJobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params?.id ? (Array.isArray(params.id) ? params.id[0] : params.id) : null;

  const [job, setJob] = useState<EmployerPublicJob | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [sessionLoading, setSessionLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // User & Candidate state
  const [currentUser, setCurrentUser] = useState<Profile | null>(null);
  const [candidateProfile, setCandidateProfile] = useState<any | null>(null);
  const [isCandidateProfileValid, setIsCandidateProfileValid] = useState<boolean>(false);

  // Application state
  const [coverNote, setCoverNote] = useState<string>("");
  const [applying, setApplying] = useState<boolean>(false);
  const [applied, setApplied] = useState<boolean>(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadJob() {
      if (!jobId) return;

      setLoading(true);
      setError(null);
      setNotFound(false);

      try {
        const jobData = await jobsApi.getPublicJob(jobId);
        if (!isMounted) return;

        if (jobData && jobData.id) {
          setJob(jobData);
        } else {
          setNotFound(true);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const errObj = err as { status?: number; message?: string } | undefined;
        if (errObj?.status === 404) {
          setNotFound(true);
        } else {
          setError(errObj?.message || "Failed to load job details. Please try again later.");
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    async function checkSession() {
      try {
        const res = await fetch("/api/auth/session", { cache: "no-store" });
        if (!res.ok) {
          if (isMounted) {
            setCurrentUser(null);
            setCandidateProfile(null);
            setIsCandidateProfileValid(false);
          }
          return;
        }
        const data = await res.json();
        if (!isMounted) return;

        if (data.authenticated && data.user) {
          setCurrentUser(data.user);

          if (data.user.role === "candidate") {
            setCandidateProfile(data.candidateProfile || null);
            setIsCandidateProfileValid(Boolean(data.isProfileComplete));

            // Check if already applied to this job
            if (jobId) {
              try {
                const existingApps = await applicationsApi.listApplications({ job_id: jobId });
                if (isMounted && existingApps && existingApps.length > 0) {
                  setApplied(true);
                }
              } catch {
                // Non-fatal if listing fails
              }
            }
          }
        } else {
          setCurrentUser(null);
          setCandidateProfile(null);
          setIsCandidateProfileValid(false);
        }
      } catch {
        if (isMounted) {
          setCurrentUser(null);
          setCandidateProfile(null);
          setIsCandidateProfileValid(false);
        }
      } finally {
        if (isMounted) setSessionLoading(false);
      }
    }

    loadJob();
    checkSession();

    // Re-check session when tab regains focus (e.g. after onboarding or login in another tab/flow)
    const onFocus = () => {
      checkSession();
    };
    window.addEventListener("focus", onFocus);

    return () => {
      isMounted = false;
      window.removeEventListener("focus", onFocus);
    };
  }, [jobId]);

  const handleApply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobId || applying || applied) return;

    setApplying(true);
    setApplyError(null);
    setApplySuccess(null);

    try {
      const res = await applicationsApi.apply(jobId, coverNote.trim() || undefined);
      if (res && (res.ok || res.application)) {
        setApplied(true);
        setApplySuccess("Application submitted successfully! The hiring team has been notified.");
      } else {
        setApplyError("Failed to submit application. Please try again.");
      }
    } catch (err: unknown) {
      const errRecord = err as { data?: { error?: string }; message?: string } | undefined;
      const errMsg = errRecord?.data?.error || (err instanceof Error ? err.message : "Failed to apply. Please try again.");
      if (errMsg.toLowerCase().includes("already applied")) {
        setApplied(true);
      }
      if (errMsg.toLowerCase().includes("complete your profile")) {
        setIsCandidateProfileValid(false);
      }
      setApplyError(errMsg);
    } finally {
      setApplying(false);
    }
  };

  const isEmployerUser = currentUser?.role === "employer";
  const isCandidateUser = currentUser?.role === "candidate";
  const isUnauthenticated = !sessionLoading && !currentUser;

  return (
    <div className="min-h-screen bg-background flex flex-col justify-between">
      <SiteHeader />

      <main className="flex-1 pt-24 pb-20">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-6">
            <Link
              href="/"
              className="hover:text-foreground flex items-center gap-1 transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Back to Jobs</span>
            </Link>
            <span>/</span>
            <span>Direct Employer Roles</span>
            {job && (
              <>
                <span>/</span>
                <span className="text-foreground font-medium truncate max-w-[200px] sm:max-w-[300px]">
                  {job.title}
                </span>
              </>
            )}
          </div>

          {/* Loading Skeleton */}
          {loading && (
            <div className="animate-pulse space-y-6">
              <div className="h-10 w-2/3 bg-muted rounded-2xl" />
              <div className="h-6 w-1/3 bg-muted rounded-full" />
              <div className="h-32 bg-muted/60 rounded-3xl" />
              <div className="h-64 bg-muted/40 rounded-3xl" />
            </div>
          )}

          {/* Error Banner */}
          {!loading && error && (
            <div className="rounded-3xl border border-destructive/20 bg-destructive/5 p-8 text-center">
              <AlertCircle className="mx-auto h-8 w-8 text-destructive" />
              <h3 className="mt-4 text-base font-semibold text-destructive">
                Error Loading Job Details
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-4 text-xs font-semibold underline hover:no-underline text-foreground"
              >
                Reload Page
              </button>
            </div>
          )}

          {/* 404 Not Found State */}
          {!loading && notFound && (
            <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center">
              <Building2 className="mx-auto h-10 w-10 text-muted-foreground" />
              <h2 className="mt-4 text-xl font-bold text-foreground">
                Job Position Unavailable
              </h2>
              <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
                This employer job posting has expired, was closed, or is no longer accepting public applications.
              </p>
              <Link
                href="/#employer-jobs"
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-2.5 text-xs font-semibold text-primary-foreground"
              >
                <span>Browse Other Active Jobs</span>
              </Link>
            </div>
          )}

          {/* Job Details Content */}
          {!loading && !notFound && job && (
            <div className="space-y-8">
              {/* Header Box */}
              <div className="rounded-3xl border border-border bg-card p-8 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                        <MapPin className="h-3.5 w-3.5 shrink-0" />
                        <span>{job.location || "Remote"}</span>
                      </span>

                      {job.work_type && (
                        <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400">
                          {job.work_type.toUpperCase()}
                        </span>
                      )}

                      {job.role_type && (
                        <span className="rounded-full border border-border bg-muted/50 px-3 py-0.5 text-xs font-medium text-muted-foreground">
                          {formatRoleType(job.role_type)}
                        </span>
                      )}
                    </div>

                    <h1 className="mt-4 text-2xl font-bold text-foreground sm:text-3xl">
                      {job.title}
                    </h1>

                    <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1.5 font-medium text-foreground">
                        <Building2 className="h-4 w-4" />
                        <span>{job.company_name}</span>
                      </div>

                      {job.company_website && (
                        <a
                          href={job.company_website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs hover:underline text-primary"
                        >
                          <Globe className="h-3.5 w-3.5" />
                          <span>Visit Website</span>
                        </a>
                      )}

                      {job.created_at && (
                        <div className="flex items-center gap-1 text-xs">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Posted {formatDate(job.created_at)}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Source Attribution Badge */}
                  <div className="flex flex-col items-end gap-2">
                    <span className="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
                      Source: {job.source_name || job.company_name}
                    </span>
                    {job.featured && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
                        <Sparkles className="h-3 w-3" />
                        <span>Featured Role</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Key Metrics Pill Grid */}
                <div className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-6 sm:grid-cols-4">
                  <div>
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      Compensation
                    </span>
                    <p className="mt-1 text-sm font-semibold text-foreground">
                      {job.salary_range || "Competitive / Unspecified"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      Experience
                    </span>
                    <p className="mt-1 text-sm font-semibold text-foreground">
                      {formatExperienceLevel(job.experience_level)}
                    </p>
                  </div>
                  <div>
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      Work Arrangement
                    </span>
                    <p className="mt-1 text-sm font-semibold text-foreground capitalize">
                      {job.work_type || "Remote"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      Role Type
                    </span>
                    <p className="mt-1 text-sm font-semibold text-foreground">
                      {formatRoleType(job.role_type)}
                    </p>
                  </div>
                </div>

                {/* Tech Stack */}
                {job.tech_stack && job.tech_stack.length > 0 && (
                  <div className="mt-6 border-t border-border pt-6">
                    <span className="text-xs font-medium text-muted-foreground">
                      Required Skills & Technologies:
                    </span>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {job.tech_stack.map((tech) => (
                        <span
                          key={tech}
                          className="rounded-lg border border-border bg-background px-3 py-1 text-xs font-mono text-foreground"
                        >
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Description Section */}
              <div className="rounded-3xl border border-border bg-card p-8 shadow-sm">
                <h2 className="text-xl font-bold text-foreground">Job Description</h2>
                <div className="mt-4 prose dark:prose-invert max-w-none text-sm leading-relaxed text-foreground whitespace-pre-line">
                  {job.description}
                </div>
              </div>

              {/* Application Section */}
              <div id="apply-section" className="rounded-3xl border border-primary/20 bg-primary/5 p-8 shadow-sm">
                <h2 className="text-xl font-bold text-foreground">
                  Apply for this Role
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Applications are reviewed directly by the hiring team at {job.company_name}.
                </p>

                {/* Session Loading State */}
                {sessionLoading && (
                  <div className="mt-6 flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                )}

                {/* Case 1: Unauthenticated Visitor */}
                {isUnauthenticated && (
                  <div className="mt-6 rounded-2xl border border-border bg-card p-6 text-center space-y-4">
                    <p className="text-sm text-foreground">
                      To apply for this verified position, please log in with your candidate account or register on PeopleRemotely.
                    </p>
                    <div className="flex flex-wrap items-center justify-center gap-4">
                      <Link
                        href={`/auth/candidate/login?next=/jobs/${job.id}`}
                        className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-2.5 text-xs font-semibold text-primary-foreground hover:opacity-95 transition-opacity"
                      >
                        <span>Log in as Candidate</span>
                      </Link>
                      <Link
                        href={`/auth/candidate/signup?next=/jobs/${job.id}`}
                        className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background px-6 py-2.5 text-xs font-semibold text-foreground hover:bg-muted transition-colors"
                      >
                        <span>Create Candidate Account</span>
                      </Link>
                    </div>
                  </div>
                )}

                {/* Case 2: Authenticated Employer (Blocked) */}
                {isEmployerUser && (
                  <div className="mt-6 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-6 text-amber-800 dark:text-amber-300">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                      <div>
                        <h4 className="font-semibold text-sm">Employer Account Detected</h4>
                        <p className="mt-1 text-xs">
                          You are currently signed in with an employer account. To apply for open positions, please sign out and sign in using a candidate account.
                        </p>
                        <div className="mt-4 flex flex-wrap items-center gap-4">
                          <Link
                            href={`/auth/candidate/login?next=/jobs/${job.id}`}
                            className="inline-flex items-center gap-1.5 text-xs font-semibold underline hover:no-underline"
                          >
                            <span>Log in as Candidate</span>
                          </Link>
                          <span className="text-muted-foreground">•</span>
                          <Link
                            href={`/auth/candidate/signup?next=/jobs/${job.id}`}
                            className="inline-flex items-center gap-1.5 text-xs font-semibold underline hover:no-underline"
                          >
                            <span>Create Candidate Account</span>
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Case 3: Authenticated Candidate */}
                {isCandidateUser && (
                  <div className="mt-6">
                    {/* Incomplete Profile Notice */}
                    {!isCandidateProfileValid ? (
                      <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-6 text-amber-800 dark:text-amber-300">
                        <div className="flex items-start gap-3">
                          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                          <div>
                            <h4 className="font-semibold text-sm">Profile Incomplete</h4>
                            <p className="mt-1 text-xs">
                              Please complete your candidate profile before applying for this job.
                            </p>
                            <Link
                              href={`/candidate/onboarding?next=/jobs/${job.id}`}
                              className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-primary text-primary-foreground px-5 py-2 text-xs font-semibold hover:opacity-90 transition-opacity"
                            >
                              <span>Complete Profile</span>
                            </Link>
                          </div>
                        </div>
                      </div>
                    ) : applied ? (
                      /* Already Applied State */
                      <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-emerald-800 dark:text-emerald-300">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0" />
                          <div>
                            <h4 className="font-semibold text-sm">Application Submitted</h4>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {applySuccess || "You have applied to this role. The employer and PeopleRemotely matching team have been notified."}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      /* Ready to Apply Form */
                      <form onSubmit={handleApply} className="space-y-4">
                        {applyError && (
                          <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
                            {applyError}
                          </div>
                        )}

                        <div>
                          <label
                            htmlFor="coverNote"
                            className="block text-xs font-medium text-foreground mb-1"
                          >
                            Add an optional note to the hiring team
                          </label>
                          <textarea
                            id="coverNote"
                            rows={3}
                            value={coverNote}
                            onChange={(e) => setCoverNote(e.target.value)}
                            placeholder="Introduce yourself or highlight why you're a great fit for this position..."
                            className="w-full rounded-2xl border border-border bg-card p-3 text-xs text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                          />
                        </div>

                        <button
                          type="submit"
                          disabled={applying}
                          className="inline-flex items-center justify-center gap-2 rounded-full bg-primary px-8 py-3 text-xs font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50"
                        >
                          {applying ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              <span>Submitting Application...</span>
                            </>
                          ) : (
                            <>
                              <Send className="h-3.5 w-3.5" />
                              <span>Submit Application</span>
                            </>
                          )}
                        </button>
                      </form>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
