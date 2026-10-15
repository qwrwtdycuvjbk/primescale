"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Building2, MapPin, DollarSign } from "lucide-react";
import { EmployerPublicJob } from "@/lib/api/jobs";

interface EmployerJobCardProps {
  job: EmployerPublicJob;
}

function formatRoleType(roleType: string): string {
  if (!roleType) return "Full-time";
  if (roleType.toLowerCase() === "c2h") return "Contract-to-Hire";
  if (roleType.toLowerCase() === "full-time") return "Full-time";
  if (roleType.toLowerCase() === "contract") return "Contract";
  return roleType.charAt(0).toUpperCase() + roleType.slice(1);
}

function formatWorkType(workType: string): string {
  if (!workType) return "Remote";
  const lower = workType.toLowerCase();
  if (lower === "remote") return "Remote";
  if (lower === "hybrid") return "Hybrid";
  if (lower === "onsite") return "Onsite";
  return workType.charAt(0).toUpperCase() + workType.slice(1);
}

export function EmployerJobCard({ job }: EmployerJobCardProps) {
  const companyName = job.company_name || job.source_name || "Verified Employer";
  const sourceLabel = job.source_name || companyName;

  return (
    <div className="flex flex-col justify-between rounded-3xl border border-border bg-card p-6 transition-transform hover:-translate-y-0.5 hover:shadow-sm">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5 min-w-0">
            {/* Location Badge */}
            <span className="inline-flex max-w-[180px] sm:max-w-[200px] items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
              <MapPin className="h-3 w-3 shrink-0" />
              <span className="truncate whitespace-nowrap">
                {job.location || "Remote"}
              </span>
            </span>

            {/* Work Mode Badge */}
            {job.work_type && (
              <span className="shrink-0 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-700 dark:text-blue-400">
                {formatWorkType(job.work_type)}
              </span>
            )}

            {/* Role Type Badge */}
            {job.role_type && (
              <span className="shrink-0 rounded-full border border-border bg-muted/40 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                {formatRoleType(job.role_type)}
              </span>
            )}
          </div>

          {/* Employer Company Source Attribution Badge */}
          <span className="shrink-0 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-0.5 text-[11px] font-medium text-primary">
            Source: {sourceLabel}
          </span>
        </div>

        {/* Job Title */}
        <h3 className="mt-4 text-lg font-semibold line-clamp-2 leading-snug">
          <Link
            href={`/jobs/${job.id}`}
            className="hover:text-primary transition-colors"
          >
            {job.title}
          </Link>
        </h3>

        {/* Company & Salary Information */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
            <Building2 className="h-3.5 w-3.5" />
            <span>{companyName}</span>
          </div>

          {job.salary_range && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-foreground bg-muted/60 rounded-full px-2.5 py-0.5">
              <DollarSign className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
              <span>{job.salary_range}</span>
            </span>
          )}
        </div>

        {/* Description Summary */}
        {job.description_summary && (
          <p className="mt-4 text-xs text-muted-foreground line-clamp-3 leading-relaxed">
            {job.description_summary}
          </p>
        )}

        {/* Tech Stack Pills */}
        {job.tech_stack && job.tech_stack.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {job.tech_stack.slice(0, 4).map((tech) => (
              <span
                key={tech}
                className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] font-mono text-muted-foreground"
              >
                {tech}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Primary CTA Button: Navigate to Internal Employer Job Details Page */}
      <div className="mt-6 border-t border-border pt-4">
        <Link
          href={`/jobs/${job.id}`}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-border bg-background py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <span>View Job Details</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
