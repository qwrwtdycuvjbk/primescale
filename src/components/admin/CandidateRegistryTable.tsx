"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Search,
  Download,
  ExternalLink,
  User,
  Power,
  CheckCircle2,
  Trash2,
} from "lucide-react";
import { CandidateAccountActionButtons } from "./CandidateAccountActionButtons";

export interface CandidateRow {
  id: string;
  user_id?: string;
  user_email?: string;
  user_full_name?: string;
  email?: string;
  full_name?: string;
  name?: string;
  headline: string;
  skills: string[];
  role_categories: string[];
  experience_level: string;
  years_experience?: number | null;
  salary_min?: number | null;
  salary_max?: number | null;
  work_authorization: string;
  us_state?: string | null;
  availability_status: string;
  profile_completeness: number;
  open_to_matching: boolean;
  resume_url?: string | null;
  source?: string | null;
  created_at?: string;
  user_is_active?: boolean;
  is_active?: boolean;
  user?: {
    id?: string;
    email?: string;
    full_name?: string;
    is_active?: boolean;
  };
  profiles?: {
    id?: string;
    email?: string;
    full_name?: string;
    phone?: string;
    role?: string;
    is_active?: boolean;
  };
}

export type AdminCandidateRow = CandidateRow;

interface Props {
  candidates?: CandidateRow[];
  initialCandidates?: CandidateRow[];
  totalCount?: number;
  activeCount?: number;
}

export function CandidateRegistryTable({
  candidates: propCandidates,
  initialCandidates,
}: Props) {
  const [candidates, setCandidates] = useState<CandidateRow[]>(
    propCandidates || initialCandidates || []
  );

  return (
    <div className="space-y-6">
      {/* Candidates Table */}
      <div className="overflow-hidden rounded-3xl border border-border bg-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-muted/40 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              <tr>
                <th className="py-4 px-6">Candidate</th>
                <th className="py-4 px-6">Headline & Skills</th>
                <th className="py-4 px-6">Status</th>
                <th className="py-4 px-6">Account Status</th>
                <th className="py-4 px-6">Source</th>
                <th className="py-4 px-6">Resume</th>
                <th className="py-4 px-6 text-right">Account Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {candidates.length > 0 ? (
                candidates.map((candidate) => {
                  const isActive =
                    candidate.user_is_active !== undefined
                      ? candidate.user_is_active
                      : candidate.is_active !== undefined
                        ? candidate.is_active
                        : (candidate.user?.is_active ?? candidate.profiles?.is_active ?? true);

                  const rawName =
                    candidate.user_full_name ||
                    candidate.full_name ||
                    candidate.name ||
                    candidate.profiles?.full_name ||
                    candidate.user?.full_name ||
                    "";
                  const name = rawName.trim() || "Anonymous Candidate";

                  const rawEmail =
                    candidate.user_email ||
                    candidate.email ||
                    candidate.profiles?.email ||
                    candidate.user?.email ||
                    "";
                  const email = rawEmail.trim() || "No email";

                  const skills = Array.isArray(candidate.skills) ? candidate.skills.slice(0, 4) : [];

                  return (
                    <tr key={candidate.id} className="transition-colors hover:bg-muted/20">
                      <td className="py-4 px-6">
                        <Link
                          href={`/admin/candidates/${candidate.id}`}
                          className="group block font-semibold text-foreground hover:text-primary transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold text-sm">
                              {(name !== "Anonymous Candidate" ? name : email).charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-semibold text-foreground group-hover:text-primary transition-colors">
                                {name}
                              </p>
                              <p className="text-xs text-muted-foreground font-mono">{email}</p>
                            </div>
                          </div>
                        </Link>
                      </td>

                      <td className="py-4 px-6 max-w-xs">
                        <p className="font-medium text-foreground text-xs truncate">
                          {candidate.headline || "No headline provided"}
                        </p>
                        {skills.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-1">
                            {skills.map((skill, i) => (
                              <span
                                key={i}
                                className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground"
                              >
                                {skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                            candidate.availability_status === "actively_looking"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : candidate.availability_status === "open"
                                ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {candidate.availability_status ? candidate.availability_status.replace("_", " ") : "Unknown"}
                        </span>
                      </td>

                      {/* Account Status */}
                      <td className="py-4 px-6 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${
                            isActive
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20"
                              : "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20"
                          }`}
                        >
                          <span className={`h-1.5 w-1.5 rounded-full ${isActive ? "bg-emerald-500" : "bg-red-500"}`} />
                          {isActive ? "Active" : "Inactive"}
                        </span>
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                          {candidate.source === "people_prime" ? "People Prime" : "Direct"}
                        </span>
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        {candidate.resume_url ? (
                          <a
                            href={`/api/admin/candidates/${candidate.id}/resume`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                          >
                            <Download className="h-3.5 w-3.5" />
                            Resume
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground">None</span>
                        )}
                      </td>

                      {/* Account Actions */}
                      <td className="py-4 px-6 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end">
                          <CandidateAccountActionButtons
                            candidateId={candidate.id}
                            candidateName={name}
                            candidateEmail={email}
                            isActive={isActive}
                            compact={true}
                            onStatusChange={(newStatus) => {
                              setCandidates((prev) =>
                                prev.map((c) =>
                                  c.id === candidate.id
                                    ? {
                                        ...c,
                                        user_is_active: newStatus,
                                        is_active: newStatus,
                                        user: c.user ? { ...c.user, is_active: newStatus } : undefined,
                                        profiles: c.profiles ? { ...c.profiles, is_active: newStatus } : undefined,
                                      }
                                    : c
                                )
                              );
                            }}
                            onDeleted={() => {
                              setCandidates((prev) => prev.filter((c) => c.id !== candidate.id));
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-muted-foreground text-sm">
                    <User className="mx-auto h-8 w-8 text-muted-foreground/40 mb-2" />
                    No candidates found matching your criteria.
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