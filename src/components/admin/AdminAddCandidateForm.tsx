"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Upload } from "lucide-react";
import Link from "next/link";
import {
  AVAILABILITY_OPTIONS,
  CANDIDATE_SOURCE_OPTIONS,
  EXPERIENCE_LEVELS,
  PRIVACY_OPTIONS,
  ROLE_CATEGORIES,
  US_STATES,
  WORK_AUTH_OPTIONS,
  WORK_TYPE_OPTIONS,
} from "@/lib/constants";
import type {
  AvailabilityStatus,
  CandidateSource,
  ExperienceLevel,
  PreferredWorkType,
  PrivacyVisibility,
} from "@/lib/types";
import type { AdminCreateCandidateInput } from "@/lib/admin-create-candidate";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  SecondaryButton,
  fieldInputClass,
} from "@/components/site/form";

const initial: AdminCreateCandidateInput = {
  fullName: "",
  email: "",
  phone: "",
  headline: "",
  currentTitle: "",
  yearsExperience: undefined,
  skills: "",
  roleCategories: [],
  experienceLevel: "mid",
  workAuthorization: "us_citizen",
  usState: "Remote (US)",
  preferredWorkType: "remote",
  availabilityStatus: "actively_looking",
  privacyVisibility: "employers_only",
  bio: "",
  githubUrl: "",
  portfolioUrl: "",
  linkedinUrl: "",
  resumeUrl: "",
  source: "people_prime",
};

export function AdminAddCandidateForm() {
  const router = useRouter();
  const [form, setForm] = useState<AdminCreateCandidateInput>(initial);
  const [status, setStatus] = useState<"idle" | "loading" | "uploading">("idle");
  const [error, setError] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  const canSubmit = useMemo(() => {
    return (
      form.fullName.trim() &&
      form.email.trim() &&
      form.headline.trim() &&
      form.skills.trim() &&
      form.roleCategories.length > 0
    );
  }, [form]);

  function toggleCategory(category: string) {
    setForm((prev) => ({
      ...prev,
      roleCategories: prev.roleCategories.includes(category)
        ? prev.roleCategories.filter((item) => item !== category)
        : [...prev.roleCategories, category],
    }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;

    setStatus("loading");
    setError("");

    try {
      const response = await fetch("/api/admin/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      const data = (await response.json()) as {
        error?: string;
        candidateProfileId?: string;
        matchesCreated?: number;
      };

      if (!response.ok) {
        setError(data.error ?? "Could not add candidate.");
        return;
      }

      if (resumeFile && data.candidateProfileId) {
        setStatus("uploading");
        const uploadData = new FormData();
        uploadData.set("file", resumeFile);

        const uploadResponse = await fetch(
          `/api/admin/candidates/${data.candidateProfileId}/resume`,
          { method: "POST", body: uploadData },
        );

        if (!uploadResponse.ok) {
          const uploadResult = (await uploadResponse.json()) as { error?: string };
          setError(
            uploadResult.error ??
              "Candidate was added, but the resume upload failed. You can upload it later.",
          );
          router.push("/admin/candidates");
          router.refresh();
          return;
        }
      }

      const matchesNote =
        data.matchesCreated && data.matchesCreated > 0
          ? ` ${data.matchesCreated} match${data.matchesCreated === 1 ? "" : "es"} created.`
          : "";

      router.push(`/admin/candidates?added=1${matchesNote ? `&matches=${data.matchesCreated}` : ""}`);
      router.refresh();
    } finally {
      setStatus("idle");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-10">
      {error && <ErrorBanner message={error} />}

      <section className="space-y-5 rounded-3xl border border-border bg-card p-6">
        <div>
          <h2 className="text-lg font-semibold">Contact</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Creates a candidate account recruiters can match and manage. They can
            claim it later via password reset on this email.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="fullName">Full name</FieldLabel>
            <input
              id="fullName"
              required
              className={fieldInputClass}
              value={form.fullName}
              onChange={(event) => setForm({ ...form, fullName: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="email">Email</FieldLabel>
            <input
              id="email"
              type="email"
              required
              className={fieldInputClass}
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="phone">Phone</FieldLabel>
            <input
              id="phone"
              className={fieldInputClass}
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="source">Source</FieldLabel>
            <select
              id="source"
              className={fieldInputClass}
              value={form.source}
              onChange={(event) =>
                setForm({ ...form, source: event.target.value as CandidateSource })
              }
            >
              {CANDIDATE_SOURCE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-5 rounded-3xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Role & experience</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FieldLabel htmlFor="headline">Headline</FieldLabel>
            <input
              id="headline"
              required
              placeholder="Senior backend engineer · Node, AWS"
              className={fieldInputClass}
              value={form.headline}
              onChange={(event) => setForm({ ...form, headline: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="currentTitle">Current title</FieldLabel>
            <input
              id="currentTitle"
              className={fieldInputClass}
              value={form.currentTitle}
              onChange={(event) => setForm({ ...form, currentTitle: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="yearsExperience">Years of experience</FieldLabel>
            <input
              id="yearsExperience"
              type="number"
              min={0}
              className={fieldInputClass}
              value={form.yearsExperience ?? ""}
              onChange={(event) =>
                setForm({
                  ...form,
                  yearsExperience: event.target.value
                    ? Number(event.target.value)
                    : undefined,
                })
              }
            />
          </div>
          <div>
            <FieldLabel htmlFor="experienceLevel">Experience level</FieldLabel>
            <select
              id="experienceLevel"
              className={fieldInputClass}
              value={form.experienceLevel}
              onChange={(event) =>
                setForm({
                  ...form,
                  experienceLevel: event.target.value as ExperienceLevel,
                })
              }
            >
              {EXPERIENCE_LEVELS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <FieldLabel htmlFor="bio">Bio</FieldLabel>
            <textarea
              id="bio"
              rows={3}
              className={fieldInputClass}
              value={form.bio}
              onChange={(event) => setForm({ ...form, bio: event.target.value })}
            />
          </div>
        </div>
      </section>

      <section className="space-y-5 rounded-3xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Skills</h2>
        <div>
          <FieldLabel htmlFor="skills">Skills (comma-separated)</FieldLabel>
          <input
            id="skills"
            required
            placeholder="TypeScript, React, Node.js, AWS"
            className={fieldInputClass}
            value={form.skills}
            onChange={(event) => setForm({ ...form, skills: event.target.value })}
          />
        </div>
        <div>
          <FieldLabel>Role categories</FieldLabel>
          <div className="mt-3 flex flex-wrap gap-2">
            {ROLE_CATEGORIES.map((category) => {
              const selected = form.roleCategories.includes(category);
              return (
                <button
                  key={category}
                  type="button"
                  onClick={() => toggleCategory(category)}
                  className={`rounded-full border px-4 py-2 text-sm transition ${
                    selected
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {category}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="space-y-5 rounded-3xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Work preferences</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="workAuthorization">Work authorization</FieldLabel>
            <select
              id="workAuthorization"
              className={fieldInputClass}
              value={form.workAuthorization}
              onChange={(event) =>
                setForm({ ...form, workAuthorization: event.target.value })
              }
            >
              {WORK_AUTH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor="usState">US state / location</FieldLabel>
            <select
              id="usState"
              className={fieldInputClass}
              value={form.usState}
              onChange={(event) => setForm({ ...form, usState: event.target.value })}
            >
              {US_STATES.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor="preferredWorkType">Work type</FieldLabel>
            <select
              id="preferredWorkType"
              className={fieldInputClass}
              value={form.preferredWorkType}
              onChange={(event) =>
                setForm({
                  ...form,
                  preferredWorkType: event.target.value as PreferredWorkType,
                })
              }
            >
              {WORK_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor="availabilityStatus">Availability</FieldLabel>
            <select
              id="availabilityStatus"
              className={fieldInputClass}
              value={form.availabilityStatus}
              onChange={(event) =>
                setForm({
                  ...form,
                  availabilityStatus: event.target.value as AvailabilityStatus,
                })
              }
            >
              {AVAILABILITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel htmlFor="salaryMin">Salary min (USD)</FieldLabel>
            <input
              id="salaryMin"
              type="number"
              min={0}
              className={fieldInputClass}
              value={form.salaryMin ?? ""}
              onChange={(event) =>
                setForm({
                  ...form,
                  salaryMin: event.target.value ? Number(event.target.value) : undefined,
                })
              }
            />
          </div>
          <div>
            <FieldLabel htmlFor="salaryMax">Salary max (USD)</FieldLabel>
            <input
              id="salaryMax"
              type="number"
              min={0}
              className={fieldInputClass}
              value={form.salaryMax ?? ""}
              onChange={(event) =>
                setForm({
                  ...form,
                  salaryMax: event.target.value ? Number(event.target.value) : undefined,
                })
              }
            />
          </div>
          <div className="sm:col-span-2">
            <FieldLabel htmlFor="privacyVisibility">Profile visibility</FieldLabel>
            <select
              id="privacyVisibility"
              className={fieldInputClass}
              value={form.privacyVisibility}
              onChange={(event) =>
                setForm({
                  ...form,
                  privacyVisibility: event.target.value as PrivacyVisibility,
                })
              }
            >
              {PRIVACY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="space-y-5 rounded-3xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Links & resume</h2>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="linkedinUrl">LinkedIn</FieldLabel>
            <input
              id="linkedinUrl"
              className={fieldInputClass}
              value={form.linkedinUrl}
              onChange={(event) => setForm({ ...form, linkedinUrl: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="githubUrl">GitHub</FieldLabel>
            <input
              id="githubUrl"
              className={fieldInputClass}
              value={form.githubUrl}
              onChange={(event) => setForm({ ...form, githubUrl: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="portfolioUrl">Portfolio</FieldLabel>
            <input
              id="portfolioUrl"
              className={fieldInputClass}
              value={form.portfolioUrl}
              onChange={(event) => setForm({ ...form, portfolioUrl: event.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="resumeFile">Resume file (optional)</FieldLabel>
            <label className="mt-2 flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground transition hover:border-primary hover:text-foreground">
              <Upload className="h-4 w-4" />
              {resumeFile ? resumeFile.name : "Upload PDF or DOCX"}
              <input
                id="resumeFile"
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="sr-only"
                onChange={(event) => setResumeFile(event.target.files?.[0] ?? null)}
              />
            </label>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton type="submit" disabled={!canSubmit || status !== "idle"}>
          {status === "loading"
            ? "Adding candidate…"
            : status === "uploading"
              ? "Uploading resume…"
              : "Add candidate"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
        <Link href="/admin/candidates">
          <SecondaryButton type="button">
            <ArrowLeft className="h-4 w-4" />
            Cancel
          </SecondaryButton>
        </Link>
      </div>
    </form>
  );
}
