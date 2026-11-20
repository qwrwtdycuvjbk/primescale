"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  ArrowRight,
  Building2,
  Calendar,
  CheckCircle2,
  DollarSign,
  ExternalLink,
  Flag,
  Globe,
  Info,
  MapPin,
  RefreshCw,
  Search,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import {
  candidatesApi,
  CandidateExternalRecommendationsResponse,
  CandidateExternalRecommendationsParams,
} from "@/lib/api";
import { ApiError } from "@/lib/api/client";

interface AiRecommendedExternalJobsSectionProps {
  token?: string;
  initialCompleteness?: number;
  initialProfileComplete?: boolean;
  initialOpenToMatching?: boolean;
  initialHasResume?: boolean;
}

export function AiRecommendedExternalJobsSection({
  token,
}: AiRecommendedExternalJobsSectionProps) {
  const [data, setData] = useState<CandidateExternalRecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{
    code?: string;
    message: string;
    status?: number;
  } | null>(null);

  // Filter / Query State
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [remoteType, setRemoteType] = useState<string>("ALL");
  const [ordering, setOrdering] = useState<string>("-final_score");
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(10);

  // Feedback Dialog State (Phase 6Z.12B)
  const [reportingRec, setReportingRec] = useState<{
    id: string;
    title: string;
    company: string;
  } | null>(null);
  const [reportReason, setReportReason] = useState<string>("not_relevant");
  const [reportComments, setReportComments] = useState<string>("");
  const [reportSubmitting, setReportSubmitting] = useState<boolean>(false);
  const [reportSuccess, setReportSuccess] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  // Search debounce: 400ms to avoid excessive API requests
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [search]);

  // Fetch recommendations
  const fetchRecommendations = useCallback(async (isCancelled?: () => boolean) => {
    setLoading(true);
    setError(null);

    const params: CandidateExternalRecommendationsParams = {
      page,
      page_size: pageSize,
      ordering,
    };
    if (debouncedSearch.trim()) {
      params.search = debouncedSearch.trim();
    }
    if (remoteType && remoteType !== "ALL") {
      params.remote_type = remoteType;
    }

    try {
      const res = await candidatesApi.getExternalRecommendations(params, { token });
      if (!isCancelled || !isCancelled()) {
        setData(res);
      }
    } catch (err: unknown) {
      if (isCancelled && isCancelled()) return;
      if (err instanceof ApiError) {
        const errData = err.data as Record<string, unknown> | undefined;
        setError({
          code: typeof errData?.code === "string" ? errData.code : undefined,
          message:
            typeof errData?.detail === "string"
              ? errData.detail
              : err.message || "Unable to load AI recommended external jobs.",
          status: err.status,
        });
      } else {
        setError({
          message: "Failed to connect to recommendation service. Please try again.",
        });
      }
    } finally {
      if (!isCancelled || !isCancelled()) {
        setLoading(false);
      }
    }
  }, [page, pageSize, ordering, debouncedSearch, remoteType, token]);

  useEffect(() => {
    let cancelled = false;
    // Asynchronous dispatch via microtask to avoid synchronous cascading setState in effect body
    const timeoutId = setTimeout(() => {
      void fetchRecommendations(() => cancelled);
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [fetchRecommendations]);

  // Format posted date
  function formatJobDate(dateStr?: string | null): string {
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

  // Format salary
  function formatSalary(
    min?: string | number | null,
    max?: string | number | null,
    currency: string = "USD",
  ): string | null {
    if (!min && !max) return null;
    const currSymbol = currency === "USD" ? "$" : currency + " ";
    const numMin = min ? Number(min).toLocaleString() : null;
    const numMax = max ? Number(max).toLocaleString() : null;

    if (numMin && numMax) return `${currSymbol}${numMin} – ${currSymbol}${numMax}/yr`;
    if (numMin) return `From ${currSymbol}${numMin}/yr`;
    if (numMax) return `Up to ${currSymbol}${numMax}/yr`;
    return null;
  }

  // Display normalization for location labels (Phase 6Z.13H)
  function formatDisplayLocation(job: { location?: string | null; country?: string | null; remote_type?: string | null }): {
    display: string;
    fullTitle?: string;
  } {
    const rawLoc = (job.location || "").trim();
    const country = (job.country || "").trim().toUpperCase();
    const isRemote = job.remote_type === "REMOTE";

    // When country is verified US and job is remote, normalize verbose multi-country strings to clean label
    if (country === "US" && isRemote) {
      if (!rawLoc || rawLoc.toLowerCase().includes("united states") || rawLoc.includes(",")) {
        return {
          display: "United States (Remote)",
          fullTitle: rawLoc && rawLoc !== "United States (Remote)" ? rawLoc : undefined,
        };
      }
    }

    const fallback = rawLoc || (country ? `${country} Remote` : "US Remote");
    return {
      display: fallback,
      fullTitle: rawLoc && rawLoc !== fallback ? rawLoc : undefined,
    };
  }

  // Safe display capitalization for matched skills (Phase 6Z.13H)
  function formatSkillDisplay(skill: string): string {
    const s = skill.trim();
    if (!s) return "";

    const canonicalMap: Record<string, string> = {
      aws: "AWS",
      django: "Django",
      javascript: "JavaScript",
      react: "React",
      sql: "SQL",
      rest: "REST",
      css: "CSS",
      html: "HTML",
      git: "Git",
      python: "Python",
      mysql: "MySQL",
      postgresql: "PostgreSQL",
      redis: "Redis",
      celery: "Celery",
      java: "Java",
      docker: "Docker",
      kubernetes: "Kubernetes",
      gcp: "GCP",
      azure: "Azure",
      graphql: "GraphQL",
      mongodb: "MongoDB",
      sqlite: "SQLite",
      typescript: "TypeScript",
      "tailwind css": "Tailwind CSS",
      "next.js": "Next.js",
      "node.js": "Node.js",
      linux: "Linux",
      bash: "Bash",
      c: "C",
      "c#": "C#",
      "c++": "C++",
      go: "Go",
    };

    const lower = s.toLowerCase();
    if (canonicalMap[lower]) {
      return canonicalMap[lower];
    }

    // Default fallback: capitalize first letter of each word
    return s.replace(/\b\w/g, (char) => char.toUpperCase());
  }

  // Submit Feedback Handler (Phase 6Z.12B)
  async function handleSubmitFeedback(e: React.FormEvent) {
    e.preventDefault();
    if (!reportingRec) return;

    setReportSubmitting(true);
    setReportError(null);
    setReportSuccess(null);

    try {
      const res = await candidatesApi.submitExternalRecommendationFeedback(
        {
          recommendation_id: reportingRec.id,
          reason: reportReason,
          comments: reportComments.trim() || undefined,
        },
        { token },
      );
      setReportSuccess(res.message || "Thank you for your feedback.");
      setTimeout(() => {
        setReportingRec(null);
        setReportComments("");
        setReportReason("not_relevant");
        setReportSuccess(null);
      }, 2000);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const errData = err.data as Record<string, unknown> | undefined;
        setReportError(
          typeof errData?.detail === "string"
            ? errData.detail
            : "Failed to submit feedback. Please try again.",
        );
      } else {
        setReportError("Failed to connect. Please try again.");
      }
    } finally {
      setReportSubmitting(false);
    }
  }

  // If external recommendations are globally disabled (kill switch), hide section entirely
  if (!loading && error && error.code === "feature_disabled") {
    return null;
  }

  return (
    <section className="mt-14" aria-labelledby="external-ai-recommendations-title">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            <span>AI Powered Discovery</span>
          </div>
          <h2
            id="external-ai-recommendations-title"
            className="display-headline mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-foreground"
          >
            AI Recommended External Jobs
          </h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            External remote opportunities matched to your profile using our hybrid AI scoring model
            (Semantic 50%, Skills 30%, Experience 20%). Qualified at &ge; 70% match score.
          </p>
        </div>

        {/* Total Count Badge */}
        {data?.summary && (
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-border bg-card px-4 py-2 text-right">
              <p className="text-xs text-muted-foreground">Top Match Score</p>
              <p className="text-lg font-bold text-foreground">
                {data.summary.highest_match_score ? `${data.summary.highest_match_score}%` : "—"}
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-card px-4 py-2 text-right">
              <p className="text-xs text-muted-foreground">Qualified Jobs</p>
              <p className="text-lg font-bold text-foreground">
                {data.summary.total_qualified}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Candidate-Facing AI Disclaimer Banner (Phase 6Z.12B) */}
      <div className="mt-5 rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Info className="h-4 w-4" />
          </div>
          <div className="flex-1 text-xs text-muted-foreground space-y-1">
            <p className="font-semibold text-foreground text-xs sm:text-sm">
              About AI Recommended External Opportunities
            </p>
            <p className="leading-relaxed">
              These external job recommendations are generated using hybrid AI matching based on your profile details, skills, experience, and publicly indexed job listings. Match percentages are estimates and do not guarantee an interview, job offer, or hiring outcome.
            </p>
            <p className="leading-relaxed text-[11px] text-muted-foreground/90">
              Role availability and requirements are maintained by third-party job providers and may change without notice. Applications are submitted directly on external employer or job board websites. Please independently verify role requirements and compensation before applying.
            </p>
          </div>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <div className="mt-6 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by job title or company name..."
            className="w-full rounded-full border border-border bg-card pl-10 pr-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Remote / Hybrid Filter */}
          <div className="flex items-center rounded-full border border-border bg-card p-1 text-xs font-medium">
            <button
              onClick={() => {
                setRemoteType("ALL");
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 transition ${
                remoteType === "ALL"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              All Types
            </button>
            <button
              onClick={() => {
                setRemoteType("REMOTE");
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 transition ${
                remoteType === "REMOTE"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Remote
            </button>
            <button
              onClick={() => {
                setRemoteType("HYBRID");
                setPage(1);
              }}
              className={`rounded-full px-3 py-1 transition ${
                remoteType === "HYBRID"
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Hybrid
            </button>
          </div>

          {/* Ordering Dropdown */}
          <select
            value={ordering}
            onChange={(e) => {
              setOrdering(e.target.value);
              setPage(1);
            }}
            className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          >
            <option value="-final_score">Highest Match Score</option>
            <option value="final_score">Lowest Match Score</option>
            <option value="-posted_at">Recently Posted</option>
            <option value="-calculated_at">Recently Matched</option>
          </select>

          {/* Refresh Button */}
          <button
            onClick={() => void fetchRecommendations()}
            disabled={loading}
            title="Refresh recommendations"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted transition"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="mt-6">
        {/* State 1: Feature Globally Disabled */}
        {error && error.code === "feature_disabled" && (
          <div className="hidden" aria-hidden="true" />
        )}

        {/* State 2: Incomplete Profile / Matching Disabled / Resume Required */}
        {error &&
          ["profile_incomplete", "profile_not_complete_flag", "resume_required"].includes(
            error.code || "",
          ) && (
            <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-8 text-center sm:text-left">
              <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-foreground">
                    Complete Your Profile to Unlock External AI Recommendations
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
                    Our AI recommendation engine requires a 100% complete profile and an uploaded resume
                    to match your technical background with active external remote jobs.
                  </p>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <Link
                      href="/candidate/onboarding"
                      className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-95 transition"
                    >
                      <span>Complete Profile & Upload Resume</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href="/candidate/profile"
                      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted transition"
                    >
                      View Profile
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}

        {/* State 2: Matching Disabled */}
        {error && error.code === "matching_disabled" && (
          <div className="rounded-3xl border border-blue-500/30 bg-blue-500/10 p-8 text-center sm:text-left">
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-500/20 text-blue-600 dark:text-blue-400">
                <Zap className="h-6 w-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-foreground">
                  Job Matching is Currently Paused
                </h3>
                <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
                  You have disabled automated matching in your profile preferences. Enable matching
                  to start seeing AI-recommended external job opportunities.
                </p>
                <div className="mt-4">
                  <Link
                    href="/candidate/profile"
                    className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-95 transition"
                  >
                    <span>Update Preferences in Profile</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* State 4: Generic / Network / Server Error (excluding feature disabled) */}
        {error &&
          ![
            "feature_disabled",
            "profile_incomplete",
            "profile_not_complete_flag",
            "resume_required",
            "matching_disabled",
          ].includes(error.code || "") && (
            <div className="rounded-3xl border border-rose-500/30 bg-rose-500/10 p-8 text-center">
              <AlertCircle className="mx-auto h-8 w-8 text-rose-500" />
              <h3 className="mt-3 text-base font-bold text-foreground">
                Unable to Load AI Recommended Jobs
              </h3>
              <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
                {error.message}
              </p>
              <button
                onClick={() => void fetchRecommendations()}
                className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-95 transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Retry</span>
              </button>
            </div>
          )}

        {/* State 4: Loading Skeleton */}
        {loading && (
          <div className="grid gap-6 md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-3xl border border-border bg-card p-6 space-y-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="h-5 bg-muted rounded w-2/3" />
                  <div className="h-8 bg-muted rounded-full w-20" />
                </div>
                <div className="h-4 bg-muted rounded w-1/3" />
                <div className="h-16 bg-muted/60 rounded-2xl" />
                <div className="flex gap-2">
                  <div className="h-6 bg-muted rounded-md w-16" />
                  <div className="h-6 bg-muted rounded-md w-16" />
                  <div className="h-6 bg-muted rounded-md w-16" />
                </div>
                <div className="h-10 bg-muted rounded-full w-full pt-2" />
              </div>
            ))}
          </div>
        )}

        {/* State 5: Recommendations Loaded */}
        {!loading && !error && data && data.results.length > 0 && (
          <>
            <div className="grid gap-6 md:grid-cols-2">
              {data.results.map((rec) => {
                const job = rec.external_job;
                const salaryStr = formatSalary(
                  job.salary_min,
                  job.salary_max,
                  job.salary_currency,
                );
                const isUrlValid = Boolean(
                  job.application_url &&
                    (job.application_url.startsWith("http://") ||
                      job.application_url.startsWith("https://")),
                );

                return (
                  <article
                    key={rec.recommendation_id}
                    className="flex flex-col justify-between rounded-3xl border border-border bg-card p-6 sm:p-7 shadow-sm transition hover:shadow-md hover:border-primary/40 relative"
                  >
                    <div>
                      {/* Top Badges: Score & Remote/Source */}
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                          {/* Match Score Badge */}
                          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                            <Sparkles className="h-3.5 w-3.5 shrink-0" />
                            <span>{rec.final_score}% Match</span>
                          </span>

                          {/* Remote / Hybrid Badge */}
                          {job.remote_type && (
                            <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-700 dark:text-blue-400">
                              {job.remote_type === "REMOTE" ? "Remote" : "Hybrid"}
                            </span>
                          )}

                          {/* Location Badge */}
                          {(() => {
                            const locInfo = formatDisplayLocation(job);
                            return (
                              <span
                                title={locInfo.fullTitle}
                                className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/50 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground"
                              >
                                <MapPin className="h-3 w-3 shrink-0" />
                                <span className="truncate max-w-[180px] sm:max-w-[220px]">
                                  {locInfo.display}
                                </span>
                              </span>
                            );
                          })()}
                        </div>

                        {/* Provider Attribution Badge */}
                        <span className="shrink-0 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                          {job.source_attribution?.attribution_name || job.source_name || "External Job"}
                        </span>
                      </div>

                      {/* Job Title & Company */}
                      <h3 className="mt-4 text-xl font-bold text-foreground leading-snug">
                        {job.job_title}
                      </h3>

                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground font-medium">
                        <div className="flex items-center gap-1 text-foreground">
                          <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{job.company_name}</span>
                        </div>

                        {job.company_website && (
                          <a
                            href={job.company_website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-primary hover:underline"
                          >
                            <Globe className="h-3 w-3" />
                            <span>Website</span>
                          </a>
                        )}

                        {job.employment_type && (
                          <span>· {job.employment_type.replace(/_/g, " ")}</span>
                        )}

                        {salaryStr && (
                          <span className="inline-flex items-center gap-0.5 text-emerald-700 dark:text-emerald-400 font-semibold">
                            <DollarSign className="h-3 w-3" />
                            <span>{salaryStr}</span>
                          </span>
                        )}

                        {job.posted_at && (
                          <span className="inline-flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            <span>Posted {formatJobDate(job.posted_at)}</span>
                          </span>
                        )}
                      </div>

                      {/* Hybrid Score Breakdown Component */}
                      <div className="mt-4 rounded-2xl border border-border bg-muted/30 p-3.5">
                        <div className="flex items-center justify-between text-xs font-semibold text-foreground mb-2">
                          <span>AI Match Breakdown</span>
                          <span className="font-mono text-[11px] text-muted-foreground">
                            50% / 30% / 20%
                          </span>
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div className="rounded-xl border border-border bg-card p-2">
                            <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                              Semantic
                            </p>
                            <p className="mt-0.5 text-sm font-bold text-foreground">
                              {rec.semantic_score}%
                            </p>
                            <p className="text-[10px] text-muted-foreground">50% wt</p>
                          </div>
                          <div className="rounded-xl border border-border bg-card p-2">
                            <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                              Skills
                            </p>
                            <p className="mt-0.5 text-sm font-bold text-foreground">
                              {rec.skill_score}%
                            </p>
                            <p className="text-[10px] text-muted-foreground">30% wt</p>
                          </div>
                          <div className="rounded-xl border border-border bg-card p-2">
                            <p className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">
                              Experience
                            </p>
                            <p className="mt-0.5 text-sm font-bold text-foreground">
                              {rec.experience_score}%
                            </p>
                            <p className="text-[10px] text-muted-foreground">20% wt</p>
                          </div>
                        </div>

                        {rec.match_reason && (
                          <p className="mt-2.5 text-[11px] text-muted-foreground leading-relaxed">
                            {rec.match_reason}
                          </p>
                        )}
                      </div>

                      {/* Matched Skills */}
                      {rec.matched_skills && rec.matched_skills.length > 0 && (
                        <div className="mt-3.5">
                          <p className="text-[11px] font-semibold text-foreground uppercase tracking-wider mb-1.5 flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                            <span>Matched Skills</span>
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {rec.matched_skills.map((skill) => (
                              <span
                                key={skill}
                                className="inline-flex items-center rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-800 dark:text-emerald-300"
                              >
                                {formatSkillDisplay(skill)}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Job Required Tech Stack */}
                      {job.tech_stack && job.tech_stack.length > 0 && (
                        <div className="mt-3">
                          <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                            Job Tech Stack
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {job.tech_stack.slice(0, 6).map((tech) => (
                              <span
                                key={tech}
                                className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] font-mono text-muted-foreground"
                              >
                                {tech}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Direct Apply CTA Button & Report Action */}
                    <div className="mt-6 border-t border-border pt-4 flex flex-col sm:flex-row items-center gap-2.5">
                      {isUrlValid ? (
                        <a
                          href={job.application_url!}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex flex-1 w-full items-center justify-center gap-2 rounded-full bg-primary px-5 py-2.5 text-xs sm:text-sm font-semibold text-primary-foreground shadow-sm transition hover:opacity-90 hover:-translate-y-0.5 active:translate-y-0"
                        >
                          <span>Apply Directly on {job.source_name || "Job Board"}</span>
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      ) : (
                        <button
                          disabled
                          className="inline-flex flex-1 w-full items-center justify-center gap-2 rounded-full border border-border bg-muted/60 px-5 py-2.5 text-xs sm:text-sm font-medium text-muted-foreground cursor-not-allowed"
                        >
                          <span>Application URL Unavailable</span>
                        </button>
                      )}

                      {/* Report / Feedback Button (Phase 6Z.12B) */}
                      <button
                        type="button"
                        onClick={() => {
                          setReportingRec({
                            id: rec.recommendation_id,
                            title: job.job_title,
                            company: job.company_name,
                          });
                          setReportReason("not_relevant");
                          setReportComments("");
                          setReportError(null);
                          setReportSuccess(null);
                        }}
                        title="Report an issue or provide feedback on this recommendation"
                        className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full border border-border bg-background px-3.5 py-2.5 text-xs font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
                      >
                        <Flag className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Report</span>
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>

            {/* Pagination Controls */}
            {data.total_pages > 1 && (
              <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-border pt-6">
                <p className="text-xs text-muted-foreground">
                  Showing page {data.current_page} of {data.total_pages} ({data.count} total recommended jobs)
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1 || loading}
                    className="rounded-full border border-border bg-card px-4 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    Previous
                  </button>
                  <span className="text-xs font-medium px-2 text-foreground">
                    {page} / {data.total_pages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                    disabled={page >= data.total_pages || loading}
                    className="rounded-full border border-border bg-card px-4 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* State 6: Empty Recommendations */}
        {!loading && !error && data && data.results.length === 0 && (
          <div className="rounded-3xl border border-dashed border-border bg-card p-12 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
              <Sparkles className="h-7 w-7" />
            </div>
            <h3 className="mt-4 text-base font-bold text-foreground">
              No AI-recommended external jobs are available right now.
            </h3>
            <p className="mt-2 text-xs sm:text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              We&apos;ll show suitable opportunities here as they become available. We continuously
              index and evaluate active remote roles against your skills and experience profile.
            </p>
            {(debouncedSearch || remoteType !== "ALL") && (
              <button
                onClick={() => {
                  setSearch("");
                  setRemoteType("ALL");
                  setPage(1);
                }}
                className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-4 py-1.5 text-xs font-semibold text-foreground hover:bg-muted transition"
              >
                <span>Clear Filters</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Feedback / Report Modal (Phase 6Z.12B) */}
      {reportingRec && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="feedback-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 sm:p-6"
        >
          <div className="relative w-full max-w-lg rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            {/* Close Button */}
            <button
              type="button"
              onClick={() => {
                if (!reportSubmitting) {
                  setReportingRec(null);
                  setReportError(null);
                  setReportSuccess(null);
                }
              }}
              disabled={reportSubmitting}
              className="absolute right-5 top-5 rounded-full p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition disabled:opacity-50"
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Close</span>
            </button>

            {/* Modal Header */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Flag className="h-5 w-5" />
              </div>
              <div>
                <h3 id="feedback-modal-title" className="text-base font-bold text-foreground">
                  Report Recommendation Issue
                </h3>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  {reportingRec.title} &middot; {reportingRec.company}
                </p>
              </div>
            </div>

            {/* Success State */}
            {reportSuccess ? (
              <div className="mt-6 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 text-center">
                <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600 dark:text-emerald-400" />
                <p className="mt-2 text-sm font-semibold text-foreground">{reportSuccess}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Your report helps refine our AI recommendation accuracy.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmitFeedback} className="mt-6 space-y-4">
                {/* Reason Selection */}
                <div>
                  <label htmlFor="report-reason" className="block text-xs font-semibold text-foreground mb-1.5">
                    What is the issue with this job recommendation?
                  </label>
                  <select
                    id="report-reason"
                    value={reportReason}
                    onChange={(e) => setReportReason(e.target.value)}
                    required
                    disabled={reportSubmitting}
                    className="w-full rounded-2xl border border-border bg-background px-3.5 py-2.5 text-xs sm:text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
                  >
                    <option value="not_relevant">Not relevant to my profile or skills</option>
                    <option value="expired_unavailable">Job appears expired, filled, or unavailable</option>
                    <option value="broken_link">Application link is broken or invalid</option>
                    <option value="inaccurate_details">Job description, title, or compensation is inaccurate</option>
                    <option value="incorrect_location">Job remote status or US location is incorrect</option>
                    <option value="other">Other issue</option>
                  </select>
                </div>

                {/* Optional Comments */}
                <div>
                  <label htmlFor="report-comments" className="block text-xs font-semibold text-foreground mb-1.5">
                    Additional Details <span className="font-normal text-muted-foreground">(Optional, max 1,000 characters)</span>
                  </label>
                  <textarea
                    id="report-comments"
                    rows={3}
                    maxLength={1000}
                    value={reportComments}
                    onChange={(e) => setReportComments(e.target.value)}
                    placeholder="Provide any additional context to help us investigate (e.g. page returned 404, requires 10+ yrs)..."
                    disabled={reportSubmitting}
                    className="w-full rounded-2xl border border-border bg-background p-3 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50 resize-none"
                  />
                  <div className="flex justify-between items-center mt-1 text-[11px] text-muted-foreground">
                    <span>Confidential &middot; Reviewed by PeopleRemotely team</span>
                    <span>{reportComments.length}/1000</span>
                  </div>
                </div>

                {/* Error Banner */}
                {reportError && (
                  <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600 dark:text-rose-400 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{reportError}</span>
                  </div>
                )}

                {/* Form Actions */}
                <div className="pt-2 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setReportingRec(null)}
                    disabled={reportSubmitting}
                    className="rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted transition disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reportSubmitting}
                    className="inline-flex items-center gap-1.5 rounded-full bg-primary px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-95 transition disabled:opacity-50"
                  >
                    {reportSubmitting ? (
                      <>
                        <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                        <span>Submitting...</span>
                      </>
                    ) : (
                      <span>Submit Report</span>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
