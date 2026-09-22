"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Building2,
  MapPin,
  Briefcase,
  DollarSign,
  Calendar,
  ExternalLink,
  ChevronLeft,
  Sparkles,
  AlertCircle,
  Tag,
  CheckCircle2,
} from "lucide-react";
import { SiteHeader } from "@/components/site/site-header";
import { SiteFooter } from "@/components/site/site-footer";
import { externalJobsApi, ExternalJob } from "@/lib/api";

function isValidUrl(url?: string | null): boolean {
  if (!url || typeof url !== "string") return false;
  const trimmed = url.trim();
  if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
    return false;
  }
  try {
    new URL(trimmed);
    return true;
  } catch {
    return false;
  }
}

function formatSalary(
  min?: number | null,
  max?: number | null,
  currency: string = "USD",
): string | null {
  if (!min && !max) return null;

  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 0,
    }).format(n);

  if (min && max) {
    if (min === max) return fmt(min);
    return `${fmt(min)} – ${fmt(max)}`;
  }
  if (min) return `From ${fmt(min)}`;
  if (max) return `Up to ${fmt(max)}`;
  return null;
}

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

export default function ExternalJobDetailPage() {
  const params = useParams<{ id: string }>();
  const jobId = params?.id ? (Array.isArray(params.id) ? params.id[0] : params.id) : null;

  const [job, setJob] = useState<ExternalJob | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    let isMounted = true;

    async function fetchJobDetail() {
      setLoading(true);
      setError(null);
      setNotFound(false);

      try {
        const data = await externalJobsApi.getExternalJob(jobId as string);
        if (isMounted) {
          if (data && data.id) {
            setJob(data);
          } else {
            setNotFound(true);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          if (err?.status === 404) {
            setNotFound(true);
          } else {
            setError(err?.message || "Failed to load job details. Please try again later.");
          }
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchJobDetail();

    return () => {
      isMounted = false;
    };
  }, [jobId]);

  const salaryDisplay = job ? formatSalary(job.salary_min, job.salary_max, job.salary_currency) : null;
  const postedDateDisplay = job ? formatDate(job.posted_at || job.created_at) : null;
  const hasValidApplyUrl = job ? isValidUrl(job.original_job_url) : false;
  const hasValidCompanyWebsite = job ? isValidUrl(job.company_website) : false;
  const hasValidLogo = job?.company_logo ? isValidUrl(job.company_logo) : false;
  const attributionUrl = job?.source_attribution?.attribution_url;
  const hasValidAttributionUrl = isValidUrl(attributionUrl);
  const attributionName = job?.source_attribution?.attribution_name || job?.source_name || "Official Source";

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
            <span>External Opportunities</span>
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
            <div className="space-y-6 animate-pulse">
              <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-6">
                <div className="flex items-start gap-4">
                  <div className="h-16 w-16 rounded-2xl bg-muted shrink-0" />
                  <div className="space-y-3 flex-1">
                    <div className="h-7 w-3/4 bg-muted rounded-full" />
                    <div className="h-4 w-1/3 bg-muted rounded-full" />
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-border">
                  <div className="h-12 bg-muted/60 rounded-xl" />
                  <div className="h-12 bg-muted/60 rounded-xl" />
                  <div className="h-12 bg-muted/60 rounded-xl" />
                  <div className="h-12 bg-muted/60 rounded-xl" />
                </div>
              </div>
              <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-4">
                <div className="h-6 w-1/4 bg-muted rounded-full" />
                <div className="h-4 w-full bg-muted/70 rounded-full" />
                <div className="h-4 w-5/6 bg-muted/70 rounded-full" />
                <div className="h-4 w-4/6 bg-muted/70 rounded-full" />
              </div>
            </div>
          )}

          {/* 404 Not Found State */}
          {!loading && notFound && (
            <div className="rounded-3xl border border-border bg-card p-10 sm:p-14 text-center space-y-5">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/70 text-muted-foreground">
                <AlertCircle className="h-7 w-7" />
              </div>
              <div className="space-y-2">
                <h2 className="text-2xl font-bold tracking-tight">Job Not Found</h2>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  This job listing may have expired, been removed by the provider, or the link is invalid.
                </p>
              </div>
              <div className="pt-2">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground shadow-sm hover:opacity-90 transition-opacity"
                >
                  Browse Available Remote Jobs
                </Link>
              </div>
            </div>
          )}

          {/* Generic Error State */}
          {!loading && !notFound && error && (
            <div className="rounded-3xl border border-destructive/20 bg-destructive/5 p-8 text-center space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <AlertCircle className="h-6 w-6" />
              </div>
              <h2 className="text-lg font-semibold text-destructive">Unable to Load Job Listing</h2>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">{error}</p>
              <div className="pt-2">
                <button
                  onClick={() => window.location.reload()}
                  className="inline-flex items-center justify-center rounded-full border border-border bg-background px-5 py-2 text-xs font-semibold hover:bg-muted transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {/* Job Details Content */}
          {!loading && !notFound && job && (
            <div className="space-y-8">
              {/* Main Job Header Card */}
              <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6">
                  <div className="flex items-start gap-4">
                    {/* Company Logo or Fallback Avatar */}
                    {hasValidLogo ? (
                      <div className="relative h-16 w-16 sm:h-20 sm:w-20 rounded-2xl border border-border bg-background p-2 shrink-0 flex items-center justify-center overflow-hidden">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={job.company_logo!}
                          alt={`${job.company_name} logo`}
                          className="h-full w-full object-contain"
                        />
                      </div>
                    ) : (
                      <div className="flex h-16 w-16 sm:h-20 sm:w-20 items-center justify-center rounded-2xl border border-border bg-muted/60 text-muted-foreground shrink-0">
                        <Building2 className="h-8 w-8" />
                      </div>
                    )}

                    <div className="space-y-1.5 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {job.department && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-0.5 text-[11px] font-semibold text-primary">
                            <Tag className="h-3 w-3" />
                            <span>{job.department}</span>
                          </span>
                        )}
                        {/* Source Attribution Badge */}
                        {hasValidAttributionUrl ? (
                          <a
                            href={attributionUrl!}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground hover:bg-muted"
                          >
                            <span>Source: {attributionName}</span>
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/60 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                            <span>Source: {attributionName}</span>
                          </span>
                        )}
                      </div>

                      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground leading-snug">
                        {job.title}
                      </h1>

                      <div className="flex flex-wrap items-center gap-3 pt-1 text-sm text-muted-foreground font-medium">
                        <span className="text-foreground">{job.company_name}</span>
                        {hasValidCompanyWebsite && (
                          <>
                            <span>•</span>
                            <a
                              href={job.company_website!}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                            >
                              <span>Visit Website</span>
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Top Apply Button (Desktop) */}
                  <div className="sm:shrink-0 flex flex-col items-start sm:items-end gap-2">
                    {hasValidApplyUrl ? (
                      <a
                        href={job.original_job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex w-full sm:w-auto items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-sm hover:opacity-90 transition-opacity"
                      >
                        <span>Apply to Job</span>
                        <ExternalLink className="h-4 w-4" />
                      </a>
                    ) : (
                      <span className="inline-flex w-full sm:w-auto items-center justify-center rounded-full border border-border bg-muted px-4 py-2.5 text-xs font-medium text-muted-foreground">
                        Application link unavailable
                      </span>
                    )}
                  </div>
                </div>

                {/* Metadata Grid */}
                <div className="mt-8 grid grid-cols-2 sm:grid-cols-4 gap-3 border-t border-border pt-6">
                  {/* Location & Remote Type */}
                  <div className="rounded-2xl border border-border/70 bg-background/50 p-3.5 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5 text-primary" />
                      <span>Location / Mode</span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-foreground truncate">
                      {job.location || (job.country === "IN" ? "India" : job.country || "Remote")}
                    </p>
                    <p className="text-[11px] text-muted-foreground capitalize">
                      {job.remote_type ? job.remote_type.toLowerCase() : "Remote"}
                    </p>
                  </div>

                  {/* Employment Type */}
                  <div className="rounded-2xl border border-border/70 bg-background/50 p-3.5 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Briefcase className="h-3.5 w-3.5 text-primary" />
                      <span>Employment Type</span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-foreground truncate">
                      {job.employment_type || "Full-time"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">Direct placement</p>
                  </div>

                  {/* Salary Range (Conditional) */}
                  <div className="rounded-2xl border border-border/70 bg-background/50 p-3.5 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <DollarSign className="h-3.5 w-3.5 text-primary" />
                      <span>Compensation</span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-foreground truncate">
                      {salaryDisplay || "Competitive"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {salaryDisplay ? job.salary_currency : "Disclosed on apply"}
                    </p>
                  </div>

                  {/* Posted Date */}
                  <div className="rounded-2xl border border-border/70 bg-background/50 p-3.5 space-y-1">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5 text-primary" />
                      <span>Date Posted</span>
                    </div>
                    <p className="text-xs sm:text-sm font-semibold text-foreground truncate">
                      {postedDateDisplay || "Recently added"}
                    </p>
                    <p className="text-[11px] text-muted-foreground">Verified active</p>
                  </div>
                </div>
              </div>

              {/* Row 2: Skills & Technologies + Candidate AI Fit */}
              <div
                className={`grid grid-cols-1 ${
                  job.tech_stack && job.tech_stack.length > 0
                    ? "md:grid-cols-2 gap-6"
                    : "gap-6"
                }`}
              >
                {/* Skills / Tech Stack Section */}
                {job.tech_stack && job.tech_stack.length > 0 && (
                  <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-4 shadow-sm flex flex-col justify-between">
                    <div>
                      <h2 className="text-lg font-bold text-foreground">
                        Skills &amp; Technologies
                      </h2>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {job.tech_stack.map((tech) => (
                          <span
                            key={tech}
                            className="inline-flex items-center gap-1 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-mono font-medium text-foreground"
                          >
                            <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                            <span>{tech}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Candidate AI Fit Card */}
                <div className="rounded-3xl border border-dashed border-border bg-muted/20 p-6 sm:p-8 space-y-3 flex flex-col justify-center">
                  <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                    <Sparkles className="h-4 w-4 text-primary/70" />
                    <span>Candidate AI Fit</span>
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
                    AI profile matching evaluates remote compatibility and role alignment based on verified candidate credentials.
                  </p>
                </div>
              </div>

              {/* Row 3: Full-Width Job Description (Matches Header Card Width) */}
              <div className="rounded-3xl border border-border bg-card p-6 sm:p-8 space-y-4 shadow-sm">
                <h2 className="text-lg font-bold text-foreground">Job Description</h2>
                <div className="text-sm sm:text-base leading-relaxed text-foreground whitespace-pre-line space-y-4">
                  {job.description ? (
                    job.description
                  ) : (
                    <p className="italic text-muted-foreground">Job description unavailable.</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
