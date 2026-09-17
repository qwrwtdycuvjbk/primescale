"use client";

import React, { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import { Search, Globe, Sparkles, ChevronRight } from "lucide-react";
import { externalJobsApi, ExternalJob } from "@/lib/api";
import { ExternalJobCard } from "@/components/site/external-job-card";

export function RemoteHybridJobs() {
  const [jobs, setJobs] = useState<ExternalJob[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedTech, setSelectedTech] = useState<string>("all");
  const [isPending, startTransition] = useTransition();

  const fetchJobs = async (search?: string, tech?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | boolean | number> = {};
      if (search && search.trim()) {
        params.search = search.trim();
      }
      if (tech && tech !== "all") {
        params.technology = tech;
      }

      // Fetch non-US external jobs with REMOTE or HYBRID work modes
      const res = await externalJobsApi.listExternalJobs({
        ...params,
        exclude_country: "US",
        remote_type: "REMOTE,HYBRID",
        page_size: 100,
      });

      setJobs(res?.results || []);
      setTotalCount(res?.count || 0);
    } catch (err: any) {
      console.warn("Could not load non-US remote/hybrid external jobs:", err);
      setError("External job listings are currently unavailable.");
      setJobs([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs(searchQuery, selectedTech);
  }, [selectedTech]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    startTransition(() => {
      fetchJobs(searchQuery, selectedTech);
    });
  };

  const techCategories = [
    { label: "All Tech", value: "all" },
    { label: "React / Next.js", value: "react" },
    { label: "Python / Django", value: "python" },
    { label: "Node.js", value: "node" },
    { label: "AWS / Cloud", value: "aws" },
    { label: "AI / ML", value: "ai" },
  ];

  const displayedJobs = jobs.slice(0, 9);
  const hasMoreJobs = jobs.length > 9 || totalCount > 9;

  return (
    <section id="remote-hybrid-jobs" className="border-t border-border bg-card/30 py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header Block */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>International &amp; Global Feeds</span>
            </div>
            <h2 className="display-headline mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              Remote / Hybrid
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Explore verified remote and hybrid opportunities aggregated from official job feeds outside the United States.
            </p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search global role or company..."
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

        {/* Category Filter Chips */}
        <div className="mt-8 flex flex-wrap gap-2">
          {techCategories.map((cat) => (
            <button
              key={cat.value}
              onClick={() => setSelectedTech(cat.value)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                selectedTech === cat.value
                  ? "bg-foreground text-background"
                  : "border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground"
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
              onClick={() => fetchJobs(searchQuery, selectedTech)}
              className="mt-4 text-xs font-semibold underline hover:no-underline"
            >
              Try reloading
            </button>
          </div>
        )}

        {/* Empty State (0 Jobs) */}
        {!loading && !error && jobs.length === 0 && (
          <div className="mt-10 rounded-3xl border border-dashed border-border bg-card p-12 text-center">
            <Globe className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-4 text-base font-semibold">No external remote or hybrid jobs available</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
              No aggregated non-US jobs match your current search filters. Check back soon as new provider feeds sync!
            </p>
            {(searchQuery || selectedTech !== "all") && (
              <button
                onClick={() => {
                  setSearchQuery("");
                  setSelectedTech("all");
                  fetchJobs("", "all");
                }}
                className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                Reset filters
              </button>
            )}
          </div>
        )}

        {/* Results Grid - Initial 9 Maximum */}
        {!loading && !error && jobs.length > 0 && (
          <>
            <div className="mt-4 text-xs text-muted-foreground font-mono">
              Showing {displayedJobs.length} of {totalCount || jobs.length} verified external listings
            </div>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {displayedJobs.map((job) => (
                <ExternalJobCard key={job.id} job={job} />
              ))}
            </div>

            {/* View More Navigates to Dedicated Page */}
            {hasMoreJobs && (
              <div className="mt-10 flex justify-center">
                <Link
                  href="/jobs/global-remote-hybrid"
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background px-8 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:bg-muted hover:text-foreground active:scale-[0.98]"
                >
                  <span>View More</span>
                  <ChevronRight className="h-4 w-4" />
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
