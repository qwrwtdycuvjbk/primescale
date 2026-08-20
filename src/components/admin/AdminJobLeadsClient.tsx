"use client";

import { useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  fieldInputClass,
} from "@/components/site/form";
import type { RemoteTechJobLead } from "@/lib/openweb-ninja";

const QUERY_PRESETS = [
  "software engineer remote UK",
  "full stack developer remote UK",
  "backend engineer remote London",
  "frontend engineer remote United Kingdom",
  "devops engineer remote UK",
  "startup software engineer remote UK",
];

const COUNTRY_OPTIONS = [
  { value: "gb", label: "United Kingdom" },
  { value: "worldwide", label: "Worldwide (UK for now)" },
  { value: "ie", label: "Ireland" },
  { value: "nl", label: "Netherlands" },
  { value: "de", label: "Germany" },
  { value: "se", label: "Sweden" },
  { value: "pt", label: "Portugal" },
  { value: "es", label: "Spain" },
  { value: "fr", label: "France" },
  { value: "au", label: "Australia" },
  { value: "sg", label: "Singapore" },
  { value: "ca", label: "Canada" },
  { value: "us", label: "United States" },
];

function formatPostedAt(value: string | null) {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function formatLocation(lead: RemoteTechJobLead) {
  const parts = [
    lead.isRemote ? "Remote" : null,
    lead.location || lead.country,
    lead.sourceLocale
      ? `via ${lead.sourceLocale.toUpperCase()}`
      : null,
  ].filter(Boolean);
  return parts.join(" · ") || "—";
}

export function AdminJobLeadsClient() {
  const [query, setQuery] = useState(QUERY_PRESETS[0]);
  const [datePosted, setDatePosted] = useState("3days");
  const [country, setCountry] = useState("gb");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [leads, setLeads] = useState<RemoteTechJobLead[]>([]);
  const [lastQuery, setLastQuery] = useState("");
  const [countriesUsed, setCountriesUsed] = useState<string[]>([]);

  async function runSearch(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        query: query.trim() || QUERY_PRESETS[0],
        datePosted,
        country,
        pages: "1",
      });

      const response = await fetch(`/api/admin/job-leads?${params}`);
      const data = (await response.json()) as {
        error?: string;
        leads?: RemoteTechJobLead[];
        queriesUsed?: string[];
        countriesUsed?: string[];
      };

      if (!response.ok) {
        setError(data.error ?? "Could not fetch job leads.");
        setLeads([]);
        setCountriesUsed([]);
        return;
      }

      setLeads(data.leads ?? []);
      setLastQuery(data.queriesUsed?.[0] ?? query);
      setCountriesUsed(data.countriesUsed ?? []);
    } catch {
      setError("Could not fetch job leads.");
      setLeads([]);
      setCountriesUsed([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <form
        onSubmit={runSearch}
        className="rounded-3xl border border-border bg-card p-6"
      >
        <div className="grid gap-4 sm:grid-cols-[1fr_160px_160px_auto] sm:items-end">
          <div>
            <FieldLabel htmlFor="query">Search query</FieldLabel>
            <input
              id="query"
              className={fieldInputClass}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="software engineer remote UK"
              list="job-lead-presets"
            />
            <datalist id="job-lead-presets">
              {QUERY_PRESETS.map((preset) => (
                <option key={preset} value={preset} />
              ))}
            </datalist>
          </div>

          <div>
            <FieldLabel htmlFor="country">Scope</FieldLabel>
            <select
              id="country"
              className={fieldInputClass}
              value={country}
              onChange={(event) => setCountry(event.target.value)}
            >
              {COUNTRY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <FieldLabel htmlFor="datePosted">Posted</FieldLabel>
            <select
              id="datePosted"
              className={fieldInputClass}
              value={datePosted}
              onChange={(event) => setDatePosted(event.target.value)}
            >
              <option value="today">Today</option>
              <option value="3days">Last 3 days</option>
              <option value="week">Last week</option>
              <option value="month">Last month</option>
            </select>
          </div>

          <PrimaryButton type="submit" disabled={loading} className="w-full sm:w-auto">
            <Search className="h-4 w-4" />
            {loading ? "Searching..." : "Find jobs"}
          </PrimaryButton>
        </div>

        <p className="mt-3 text-xs text-muted-foreground">
          UK mode only keeps jobs that mention UK / London / £ etc. (the API
          often leaves country blank, so we can’t trust location fields).
          Restart the local server if you don’t see this change. Not live on
          production until you deploy. 1 API call per search.
        </p>
      </form>

      {error && <ErrorBanner message={error} />}

      {leads.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {leads.length} lead{leads.length === 1 ? "" : "s"} for “{lastQuery}”
            {countriesUsed.length > 0
              ? ` · locales ${countriesUsed.map((c) => c.toUpperCase()).join(", ")}`
              : ""}
          </p>

          <div className="overflow-hidden rounded-3xl border border-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Company</th>
                  <th className="px-4 py-3 font-medium">Posted</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3 font-medium">Links</th>
                </tr>
              </thead>
              <tbody>
                {leads.map((lead) => (
                  <tr key={lead.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-4 align-top">
                      <p className="font-medium text-foreground">{lead.title}</p>
                      {lead.descriptionPreview && (
                        <p className="mt-1 max-w-md text-xs text-muted-foreground line-clamp-2">
                          {lead.descriptionPreview}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-4 align-top">
                      <p className="font-medium">{lead.company}</p>
                      {lead.publisher && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          via {lead.publisher}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-4 align-top text-muted-foreground">
                      {formatPostedAt(lead.postedAt)}
                    </td>
                    <td className="px-4 py-4 align-top text-muted-foreground">
                      {formatLocation(lead)}
                    </td>
                    <td className="px-4 py-4 align-top">
                      <div className="flex flex-col gap-2">
                        {lead.applyUrl && (
                          <a
                            href={lead.applyUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:text-foreground"
                          >
                            Job post
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}
                        {lead.companyWebsite && (
                          <a
                            href={lead.companyWebsite}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                          >
                            Website
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !error && leads.length === 0 && lastQuery && (
        <p className="text-sm text-muted-foreground">No leads found for that search.</p>
      )}
    </div>
  );
}
