"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Search,
  Building2,
  Globe,
  MapPin,
  Mail,
  Calendar,
  Briefcase,
  ExternalLink,
  Users,
} from "lucide-react";
import type { DjangoAdminEmployer } from "@/lib/api/companies";

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface Props {
  initialEmployers: DjangoAdminEmployer[];
  totalCount: number;
  activeCount: number;
}

export function EmployersRegistryTable({
  initialEmployers,
  totalCount,
  activeCount,
}: Props) {
  const [employers] = useState<DjangoAdminEmployer[]>(initialEmployers);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [industryFilter, setIndustryFilter] = useState("all");

  // Derive unique industries for filter dropdown
  const industries = Array.from(
    new Set(employers.map((e) => e.industry).filter(Boolean) as string[])
  ).sort();

  const filtered = employers.filter((e) => {
    if (statusFilter === "active" && !e.is_active) return false;
    if (statusFilter === "inactive" && e.is_active) return false;
    if (industryFilter !== "all" && e.industry !== industryFilter) return false;

    if (search.trim()) {
      const q = search.toLowerCase();
      const name = (e.name || "").toLowerCase();
      const email = (e.primary_contact_email || "").toLowerCase();
      const contactName = (e.primary_contact_name || "").toLowerCase();
      const location = (e.location || "").toLowerCase();
      const industry = (e.industry || "").toLowerCase();
      return (
        name.includes(q) ||
        email.includes(q) ||
        contactName.includes(q) ||
        location.includes(q) ||
        industry.includes(q)
      );
    }

    return true;
  });

  return (
    <div className="space-y-6">
      {/* Search & Filter Bar */}
      <div className="rounded-3xl border border-border bg-card p-4 sm:p-6 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by company name, contact, email, location, industry..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-2xl border border-border bg-background pl-10 pr-4 py-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-2xl border border-border bg-background px-3.5 py-2.5 text-xs font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="all">All Account Status</option>
              <option value="active">Active Accounts</option>
              <option value="inactive">Inactive Accounts</option>
            </select>

            {industries.length > 0 && (
              <select
                value={industryFilter}
                onChange={(e) => setIndustryFilter(e.target.value)}
                className="rounded-2xl border border-border bg-background px-3.5 py-2.5 text-xs font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="all">All Industries</option>
                {industries.map((ind) => (
                  <option key={ind} value={ind}>
                    {ind}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      </div>

      {/* Employers Table */}
      <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-muted/40 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              <tr>
                <th className="py-4 px-6">Company / Employer</th>
                <th className="py-4 px-6">Primary Contact</th>
                <th className="py-4 px-6">Location</th>
                <th className="py-4 px-6">Account Status</th>
                <th className="py-4 px-6">Jobs Posted</th>
                <th className="py-4 px-6">Website</th>
                <th className="py-4 px-6">Registered</th>
                <th className="py-4 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.length > 0 ? (
                filtered.map((employer) => {
                  const companyName = employer.name || employer.primary_contact_name || "Employer Account";

                  return (
                    <tr key={employer.id} className="transition-colors hover:bg-muted/20">
                      {/* Company Name */}
                      <td className="py-4 px-6">
                        <Link
                          href={`/admin/employers/${employer.id}`}
                          className="group block font-semibold text-foreground hover:text-primary transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold text-sm">
                              {companyName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                                {companyName}
                              </p>
                              {employer.industry && (
                                <p className="text-xs text-muted-foreground">{employer.industry}</p>
                              )}
                            </div>
                          </div>
                        </Link>
                      </td>

                      {/* Primary Contact */}
                      <td className="py-4 px-6">
                        <p className="font-medium text-foreground text-xs">
                          {employer.primary_contact_name || "—"}
                        </p>
                        <p className="text-xs text-muted-foreground font-mono">
                          {employer.primary_contact_email || "—"}
                        </p>
                      </td>

                      {/* Location */}
                      <td className="py-4 px-6 whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <MapPin className="h-3.5 w-3.5 shrink-0" />
                          <span>{employer.location || "Remote / US"}</span>
                        </div>
                      </td>

                      {/* Account Status */}
                      <td className="py-4 px-6 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${
                            employer.is_active
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                              : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              employer.is_active ? "bg-emerald-500" : "bg-red-500"
                            }`}
                          />
                          {employer.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>

                      {/* Jobs Posted */}
                      <td className="py-4 px-6 whitespace-nowrap">
                        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-foreground">
                          {employer.jobs_count ?? 0} {employer.jobs_count === 1 ? "job" : "jobs"}
                        </span>
                      </td>

                      {/* Website */}
                      <td className="py-4 px-6 whitespace-nowrap">
                        {employer.website ? (
                          <a
                            href={employer.website.startsWith("http") ? employer.website : `https://${employer.website}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                          >
                            <Globe className="h-3.5 w-3.5" />
                            Visit site
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>

                      {/* Registered */}
                      <td className="py-4 px-6 whitespace-nowrap text-xs text-muted-foreground">
                        {formatDate(employer.created_at)}
                      </td>

                      {/* Actions */}
                      <td className="py-4 px-6 text-right whitespace-nowrap">
                        <Link
                          href={`/admin/employers/${employer.id}`}
                          className="inline-flex items-center gap-1 text-xs font-medium text-foreground hover:text-primary underline"
                        >
                          View details
                          <ExternalLink className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-muted-foreground text-sm">
                    <Building2 className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                    No employers found matching your criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}