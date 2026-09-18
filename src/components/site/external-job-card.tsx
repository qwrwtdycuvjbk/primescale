"use client";

import React from "react";
import { ExternalLink, Building2, MapPin } from "lucide-react";
import { ExternalJob } from "@/lib/api";
import { stripHtml } from "@/lib/utils";

interface ExternalJobCardProps {
  job: ExternalJob;
}

export function ExternalJobCard({ job }: ExternalJobCardProps) {
  const cleanDescription = stripHtml(job.description);

  return (
    <div className="flex flex-col justify-between rounded-3xl border border-border bg-card p-6 transition-transform hover:-translate-y-0.5 hover:shadow-sm">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5 min-w-0">
            <span className="inline-flex max-w-[180px] sm:max-w-[200px] items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
              <MapPin className="h-3 w-3 shrink-0" />
              <span className="truncate whitespace-nowrap">
                {job.location || (job.country === "IN" ? "India" : job.country || "Remote")}
              </span>
            </span>
            {job.remote_type && (job.remote_type === "REMOTE" || job.remote_type === "HYBRID") && (
              <span className="shrink-0 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-700 dark:text-blue-400">
                {job.remote_type === "REMOTE" ? "Remote" : "Hybrid"}
              </span>
            )}
          </div>

          {/* Source Provider Attribution Badge */}
          <span className="shrink-0 rounded-full border border-border bg-muted/50 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            Source: {job.source_attribution?.attribution_name || job.source_name}
          </span>
        </div>

        <h3 className="mt-4 text-lg font-semibold line-clamp-2 leading-snug">
          {job.title}
        </h3>

        <div className="mt-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
            <Building2 className="h-3.5 w-3.5" />
            <span>{job.company_name}</span>
          </div>
          {job.department && (
            <span className="text-[11px] font-medium text-muted-foreground bg-muted/60 rounded px-2 py-0.5">
              {job.department}
            </span>
          )}
        </div>

        {cleanDescription && (
          <p className="mt-4 text-xs text-muted-foreground line-clamp-3 leading-relaxed">
            {cleanDescription}
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

      {/* Primary CTA Button: Open Original External Job URL in New Tab */}
      <div className="mt-6 border-t border-border pt-4">
        <a
          href={job.original_job_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-border bg-background py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <span>View Job on {job.source_attribution?.attribution_name || job.source_name}</span>
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  );
}
