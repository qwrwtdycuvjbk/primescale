"use client";

import React, { useEffect, useState, useTransition, useMemo } from "react";
import Link from "next/link";
import { Search, Globe, Sparkles, ChevronRight } from "lucide-react";
import { externalJobsApi, ExternalJob } from "@/lib/api";
import { ExternalJobCard } from "@/components/site/external-job-card";
import { DEPARTMENTS } from "@/lib/departments";

export function DepartmentJobs() {
  const [allJobs, setAllJobs] = useState<ExternalJob[]>([]);
  const [selectedDept, setSelectedDept] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedTech, setSelectedTech] = useState<string>("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  // Load active external jobs once to compute counts efficiently without N+1 requests
  const fetchAllJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await externalJobsApi.listExternalJobs({
        page_size: 100,
      });
      setAllJobs(res?.results || []);
    } catch (err: any) {
      console.warn("Could not load external jobs by department:", err);
      setError("Department job listings are currently unavailable.");
      setAllJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllJobs();
  }, []);

  // Compute live job count per department from loaded data
  const departmentCounts = useMemo(() => {
    const counts: Record<string, number> = { all: allJobs.length };
    for (const dept of DEPARTMENTS) {
      if (dept.code !== "all") {
        counts[dept.code] = 0;
      }
    }

    for (const job of allJobs) {
      const deptName = (job.department || "Other").toLowerCase();
      for (const dept of DEPARTMENTS) {
        if (
          dept.code !== "all" &&
          (deptName === dept.label.toLowerCase() ||
            deptName === dept.code ||
            (dept.code === "other" && deptName === "other"))
        ) {
          counts[dept.code] = (counts[dept.code] || 0) + 1;
        }
      }
    }
    return counts;
  }, [allJobs]);

  // Filter jobs based on department, search query, and tech tag
  const filteredJobs = useMemo(() => {
    return allJobs.filter((job) => {
      // Department filter
      if (selectedDept !== "all") {
        const deptObj = DEPARTMENTS.find((d) => d.code === selectedDept);
        const jobDept = (job.department || "Other").toLowerCase();
        if (selectedDept === "other") {
          if (jobDept !== "other") return false;
        } else if (
          deptObj &&
          jobDept !== deptObj.label.toLowerCase() &&
          jobDept !== selectedDept
        ) {
          return false;
        }
      }

      // Tech Stack filter
      if (selectedTech !== "all") {
        const hasTech = job.tech_stack?.some((t) =>
          t.toLowerCase().includes(selectedTech.toLowerCase()),
        );
        const inTitleOrDesc =
          job.title.toLowerCase().includes(selectedTech.toLowerCase()) ||
          job.description?.toLowerCase().includes(selectedTech.toLowerCase());
        if (!hasTech && !inTitleOrDesc) {
          return false;
        }
      }

      // Search Query filter
      if (searchQuery && searchQuery.trim()) {
        const terms = searchQuery.trim().toLowerCase().split(" ");
        const blob = `${job.title} ${job.company_name} ${job.location || ""} ${job.description || ""}`.toLowerCase();
        const matchesAll = terms.every((term) => blob.includes(term));
        if (!matchesAll) return false;
      }

      return true;
    });
  }, [allJobs, selectedDept, selectedTech, searchQuery]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
  };

  const techCategories = [
    { label: "All Tech", value: "all" },
    { label: "React / Next.js", value: "react" },
    { label: "Python / Django", value: "python" },
    { label: "Node.js", value: "node" },
    { label: "AWS / Cloud", value: "aws" },
    { label: "AI / ML", value: "ai" },
  ];

  const displayedJobs = filteredJobs.slice(0, 9);
  const hasMoreJobs = filteredJobs.length > 9;
  const currentDeptLabel = DEPARTMENTS.find((d) => d.code === selectedDept)?.label || "Department";
  const viewMoreHref = selectedDept === "all" ? "/jobs/department/all" : `/jobs/department/${selectedDept}`;

  return (
    <section id="departments" className="border-t border-border bg-card/20 py-20">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Header Block */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Technology Index</span>
            </div>
            <h2 className="display-headline mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              Jobs by Technology
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Discover active technical and operational opportunities organized by functional specialty.
            </p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 max-w-md w-full">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search within technologies..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-full border border-border bg-background py-2.5 pl-9 pr-4 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="rounded-full border border-border bg-background px-4 py-2.5 text-xs font-semibold text-muted-foreground hover:text-foreground"
              >
                Clear
              </button>
            )}
          </form>
        </div>

        {/* Department Grid Cards */}
        <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {DEPARTMENTS.map((dept) => {
            const Icon = dept.icon;
            const isSelected = selectedDept === dept.code;
            const count = departmentCounts[dept.code] ?? 0;

            return (
              <button
                key={dept.code}
                onClick={() => {
                  startTransition(() => {
                    setSelectedDept(dept.code);
                  });
                }}
                className={`group flex flex-col justify-between rounded-2xl border p-4 text-left transition-all ${
                  isSelected
                    ? "border-primary bg-primary text-primary-foreground shadow-sm"
                    : "border-border bg-card/60 hover:border-border/80 hover:bg-card text-foreground"
                }`}
              >
                <div className="flex items-center justify-between">
                  <Icon
                    className={`h-5 w-5 transition-colors ${
                      isSelected ? "text-primary-foreground" : "text-muted-foreground group-hover:text-primary"
                    }`}
                  />
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-mono font-medium ${
                      isSelected
                        ? "bg-primary-foreground/20 text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {count}
                  </span>
                </div>
                <div className="mt-3">
                  <div className="text-xs font-semibold leading-tight line-clamp-1">
                    {dept.label}
                  </div>
                  <div
                    className={`mt-0.5 text-[10px] ${
                      isSelected ? "text-primary-foreground/80" : "text-muted-foreground"
                    }`}
                  >
                    {count === 1 ? "1 job" : `${count} jobs`}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Category Filter Chips */}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
          <div className="flex flex-wrap gap-2">
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

          {selectedDept !== "all" && (
            <button
              onClick={() => setSelectedDept("all")}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
            >
              <span>Showing: {currentDeptLabel}</span>
              <span className="text-[11px] text-muted-foreground">(Reset to All)</span>
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
              onClick={fetchAllJobs}
              className="mt-4 text-xs font-semibold underline hover:no-underline"
            >
              Try reloading
            </button>
          </div>
        )}

        {/* Empty State (0 Jobs for department / search) */}
        {!loading && !error && filteredJobs.length === 0 && (
          <div className="mt-10 rounded-3xl border border-dashed border-border bg-card p-12 text-center">
            <Globe className="mx-auto h-8 w-8 text-muted-foreground" />
            <h3 className="mt-4 text-base font-semibold">No jobs currently available in this department</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
              No aggregated listings match {selectedDept !== "all" ? `the ${currentDeptLabel} department` : "your current search filters"}. Check back soon as new provider feeds sync!
            </p>
            {(selectedDept !== "all" || searchQuery || selectedTech !== "all") && (
              <button
                onClick={() => {
                  setSelectedDept("all");
                  setSearchQuery("");
                  setSelectedTech("all");
                }}
                className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                Reset all filters
              </button>
            )}
          </div>
        )}

        {/* Results Grid - Initial 9 Maximum */}
        {!loading && !error && filteredJobs.length > 0 && (
          <>
            <div className="mt-6 text-xs text-muted-foreground font-mono">
              Showing {displayedJobs.length} of {filteredJobs.length} verified listings
              {selectedDept !== "all" && ` in ${currentDeptLabel}`}
            </div>
            <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {displayedJobs.map((job) => (
                <ExternalJobCard key={job.id} job={job} />
              ))}
            </div>

            {/* View More Navigates to Dedicated Dynamic Department Page */}
            {hasMoreJobs && (
              <div className="mt-10 flex justify-center">
                <Link
                  href={viewMoreHref}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-border bg-background px-8 py-3 text-sm font-semibold text-foreground shadow-sm transition-all hover:bg-muted hover:text-foreground active:scale-[0.98]"
                >
                  <span>View More in {currentDeptLabel}</span>
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
