"use client";

import React, { useEffect, useState, useTransition, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Search, Globe, Sparkles, ChevronLeft } from "lucide-react";
import { SiteHeader } from "@/components/site/site-header";
import { SiteFooter } from "@/components/site/site-footer";
import { ExternalJobCard } from "@/components/site/external-job-card";
import { JobPagination } from "@/components/site/job-pagination";
import { externalJobsApi, ExternalJob } from "@/lib/api";
import { DEPARTMENTS, getDepartmentBySlug } from "@/lib/departments";

const PAGE_SIZE = 24;

const TECH_CATEGORIES = [
  { label: "All Tech", value: "all" },
  { label: "React / Next.js", value: "react" },
  { label: "Python / Django", value: "python" },
  { label: "Node.js", value: "node" },
  { label: "AWS / Cloud", value: "aws" },
  { label: "AI / ML", value: "ai" },
];

export default function DepartmentJobsPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const slug = params?.slug ? (Array.isArray(params.slug) ? params.slug[0] : params.slug) : "all";

  const departmentInfo = getDepartmentBySlug(slug);
  const DeptIcon = departmentInfo.icon;

  const [jobs, setJobs] = useState<ExternalJob[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [appliedSearch, setAppliedSearch] = useState<string>("");
  const [selectedTech, setSelectedTech] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  const fetchJobs = useCallback(
    async (deptSlug: string, page: number, search: string, tech: string) => {
      setLoading(true);
      setError(null);
      try {
        const queryParams: Record<string, string | boolean | number> = {
          page,
          page_size: PAGE_SIZE,
        };

        if (deptSlug && deptSlug !== "all") {
          queryParams.department = deptSlug;
        }
        if (search.trim()) {
          queryParams.search = search.trim();
        }
        if (tech !== "all") {
          queryParams.technology = tech;
        }

        const res = await externalJobsApi.listExternalJobs(queryParams);
        setJobs(res?.results || []);
        setTotalCount(res?.count || 0);
        setTotalPages(res?.total_pages || Math.ceil((res?.count || 0) / PAGE_SIZE) || 1);
      } catch (err: any) {
        console.warn("Could not load department jobs:", err);
        setError("Department job listings are currently unavailable.");
        setJobs([]);
        setTotalCount(0);
        setTotalPages(1);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchJobs(slug, currentPage, appliedSearch, selectedTech);
  }, [slug, currentPage, appliedSearch, selectedTech, fetchJobs]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(() => {
      setCurrentPage(1);
      setAppliedSearch(searchQuery);
    });
  };

  const handleDepartmentSwitch = (newSlug: string) => {
    if (newSlug === slug) return;
    setCurrentPage(1);
    router.push(`/jobs/department/${newSlug}`);
  };

  const handleTechChange = (tech: string) => {
    setSelectedTech(tech);
    setCurrentPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleResetFilters = () => {
    setSearchQuery("");
    setAppliedSearch("");
    setSelectedTech("all");
    setCurrentPage(1);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-between">
      <SiteHeader />

      <main className="flex-1 pt-24 pb-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-6">
            <Link href="/" className="hover:text-foreground flex items-center gap-1 transition-colors">
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Back to Home</span>
            </Link>
            <span>/</span>
            <Link href="/#departments" className="hover:text-foreground transition-colors">
              Jobs by Technology
            </Link>
            <span>/</span>
            <span className="text-foreground font-medium">{departmentInfo.label}</span>
          </div>

          {/* Header Block */}
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 border-b border-border pb-8">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
                <DeptIcon className="h-3.5 w-3.5" />
                <span>Department Category</span>
              </div>
              <h1 className="display-headline mt-3 text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl">
                {departmentInfo.label} Jobs
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                {departmentInfo.description}
              </p>
            </div>

            {/* Search Form */}
            <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={`Search in ${departmentInfo.label}...`}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full rounded-full border border-border bg-background py-2.5 pl-9 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
              <button
                type="submit"
                disabled={isPending}
                className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                Search
              </button>
            </form>
          </div>

          {/* Department Switcher Tabs */}
          <div className="mt-6 flex flex-wrap gap-2">
            {DEPARTMENTS.map((dept) => {
              const isSelected = dept.code === slug;
              const Icon = dept.icon;
              return (
                <button
                  key={dept.code}
                  onClick={() => handleDepartmentSwitch(dept.code)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all ${
                    isSelected
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{dept.label}</span>
                </button>
              );
            })}
          </div>

          {/* Category Filter Chips */}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
            <div className="flex flex-wrap gap-2">
              {TECH_CATEGORIES.map((cat) => (
                <button
                  key={cat.value}
                  onClick={() => handleTechChange(cat.value)}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                    selectedTech === cat.value
                      ? "bg-foreground text-background shadow-sm"
                      : "border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {(appliedSearch || selectedTech !== "all") && (
              <button
                onClick={handleResetFilters}
                className="text-xs font-semibold text-primary hover:underline"
              >
                Reset all filters
              </button>
            )}
          </div>

          {/* Loading State */}
          {loading && (
            <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map((idx) => (
                <div
                  key={idx}
                  className="animate-pulse rounded-3xl border border-border bg-card p-6 space-y-4"
                >
                  <div className="h-5 w-3/4 bg-muted rounded-full" />
                  <div className="h-4 w-1/2 bg-muted rounded-full" />
                  <div className="h-16 bg-muted/60 rounded-2xl" />
                  <div className="flex gap-2 pt-2">
                    <div className="h-6 w-16 bg-muted rounded-full" />
                    <div className="h-6 w-16 bg-muted rounded-full" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Error State */}
          {!loading && error && (
            <div className="mt-10 rounded-3xl border border-destructive/20 bg-destructive/5 p-8 text-center">
              <p className="text-sm font-medium text-destructive">{error}</p>
              <button
                onClick={() => fetchJobs(slug, currentPage, appliedSearch, selectedTech)}
                className="mt-4 text-xs font-semibold underline hover:no-underline"
              >
                Try reloading
              </button>
            </div>
          )}

          {/* Empty State */}
          {!loading && !error && jobs.length === 0 && (
            <div className="mt-10 rounded-3xl border border-dashed border-border bg-card p-12 text-center">
              <Globe className="mx-auto h-8 w-8 text-muted-foreground" />
              <h2 className="mt-4 text-base font-semibold">
                No jobs currently found in {departmentInfo.label}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
                No active listings match your selected department and filter criteria. Check back soon as new provider feeds sync!
              </p>
              {(appliedSearch || selectedTech !== "all") && (
                <button
                  onClick={handleResetFilters}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                >
                  Reset filters
                </button>
              )}
            </div>
          )}

          {/* Results Grid */}
          {!loading && !error && jobs.length > 0 && (
            <>
              <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {jobs.map((job) => (
                  <ExternalJobCard key={job.id} job={job} />
                ))}
              </div>

              {/* Server-Side Pagination */}
              <JobPagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalCount={totalCount}
                pageSize={PAGE_SIZE}
                onPageChange={handlePageChange}
                isLoading={loading}
              />
            </>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
