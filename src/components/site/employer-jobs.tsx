"use client";

import React, { useEffect, useState, useTransition } from "react";
import { Search, Sparkles, Building, ChevronDown } from "lucide-react";
import { jobsApi, EmployerPublicJob } from "@/lib/api/jobs";
import { EmployerJobCard } from "@/components/site/employer-job-card";

export function EmployerJobs() {
  const [jobs, setJobs] = useState<EmployerPublicJob[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedTech, setSelectedTech] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  const fetchJobs = React.useCallback(
    async (
      search?: string,
      tech?: string,
      pageNum: number = 1,
      append: boolean = false,
    ) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
        setError(null);
      }

      try {
        const params: Record<string, string | number> = {
          page: pageNum,
          page_size: 9,
        };

        if (search && search.trim()) {
          params.search = search.trim();
        }

        if (tech && tech !== "all") {
          params.technology = tech;
        }

        const res = await jobsApi.listPublicJobs(params);
        const incoming = res?.results || [];

        if (append) {
          setJobs((prev) => [...prev, ...incoming]);
        } else {
          setJobs(incoming);
        }
        setTotalCount(res?.count || 0);
        setPage(pageNum);
      } catch (err: unknown) {
        console.warn("Could not load employer jobs:", err);
        if (!append) {
          setError("Employer job listings are currently unavailable.");
          setJobs([]);
          setTotalCount(0);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [],
  );

  useEffect(() => {
    let ignore = false;
    const params: Record<string, string | number> = {
      page: 1,
      page_size: 9,
    };
    if (searchQuery && searchQuery.trim()) {
      params.search = searchQuery.trim();
    }
    if (selectedTech && selectedTech !== "all") {
      params.technology = selectedTech;
    }

    jobsApi
      .listPublicJobs(params)
      .then((res) => {
        if (!ignore) {
          setJobs(res?.results || []);
          setTotalCount(res?.count || 0);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          console.warn("Could not load employer jobs:", err);
          setError("Employer job listings are currently unavailable.");
          setJobs([]);
          setTotalCount(0);
          setLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTech]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(() => {
      fetchJobs(searchQuery, selectedTech, 1, false);
    });
  };

  const handleLoadMore = () => {
    const nextPage = page + 1;
    fetchJobs(searchQuery, selectedTech, nextPage, true);
  };

  const techCategories = [
    { label: "All Tech", value: "all" },
    { label: "React / Next.js", value: "react" },
    { label: "Python / Django", value: "python" },
    { label: "Node.js", value: "node" },
    { label: "AWS / Cloud", value: "aws" },
    { label: "AI / ML", value: "ai" },
  ];

  const hasMore = jobs.length < totalCount;

  return (
    <section id="employer-jobs" className="border-t border-border bg-background py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header Block */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Direct Employer Roles</span>
            </div>
            <h2 className="display-headline mt-3 text-3xl font-bold tracking-tight sm:text-4xl text-foreground">
              Jobs by Employer
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Explore open positions posted directly by companies on PeopleRemotely.
            </p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search company or tech stack..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-full border border-border bg-card py-2.5 pl-9 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary text-foreground placeholder:text-muted-foreground"
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

        {/* Tech Filter Chips */}
        <div className="mt-8 flex flex-wrap gap-2">
          {techCategories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setSelectedTech(cat.value)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                selectedTech === cat.value
                  ? "bg-foreground text-background"
                  : "border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((idx) => (
              <div
                key={idx}
                className="animate-pulse rounded-3xl border border-border bg-card p-6 space-y-4"
              >
                <div className="flex justify-between items-center">
                  <div className="h-5 w-24 bg-muted rounded-full" />
                  <div className="h-5 w-28 bg-muted rounded-full" />
                </div>
                <div className="h-6 w-3/4 bg-muted rounded-full" />
                <div className="h-4 w-1/3 bg-muted rounded-full" />
                <div className="h-14 bg-muted/60 rounded-2xl" />
                <div className="flex gap-2 pt-2">
                  <div className="h-6 w-16 bg-muted rounded-full" />
                  <div className="h-6 w-16 bg-muted rounded-full" />
                </div>
                <div className="h-9 w-full bg-muted rounded-full pt-2" />
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="mt-10 rounded-3xl border border-destructive/20 bg-destructive/5 p-8 text-center">
            <p className="text-sm font-medium text-destructive">{error}</p>
            <button
              onClick={() => fetchJobs(searchQuery, selectedTech, 1, false)}
              className="mt-4 text-xs font-semibold underline hover:no-underline text-foreground"
            >
              Try reloading
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && jobs.length === 0 && (
          <div className="mt-10 rounded-3xl border border-dashed border-border bg-card p-12 text-center">
            <Building className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-4 text-base font-semibold text-foreground">
              No employer-posted jobs available
            </h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
              No direct employer positions currently match your query. Check back soon as new verified hiring partners post roles!
            </p>
            {(searchQuery || selectedTech !== "all") && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setSelectedTech("all");
                  fetchJobs("", "all", 1, false);
                }}
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
            <div className="mt-4 text-xs text-muted-foreground font-mono">
              Showing {jobs.length} of {totalCount} verified direct roles
            </div>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {jobs.map((job) => (
                <EmployerJobCard key={job.id} job={job} />
              ))}
            </div>

            {/* Load More Button */}
            {hasMore && (
              <div className="mt-10 flex justify-center">
                <button
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-card px-8 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:bg-muted hover:text-foreground active:scale-[0.98] disabled:opacity-50"
                >
                  <span>{loadingMore ? "Loading more..." : "Load More Roles"}</span>
                  <ChevronDown className="h-4 w-4" />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
