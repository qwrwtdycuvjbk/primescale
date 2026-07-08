"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Upload } from "lucide-react";
import {
  AVAILABILITY_OPTIONS,
  EXPERIENCE_LEVELS,
  PRIVACY_OPTIONS,
  ROLE_CATEGORIES,
  US_STATES,
  WORK_AUTH_OPTIONS,
  WORK_TYPE_OPTIONS,
} from "@/lib/constants";
import { calculateProfileCompleteness } from "@/lib/profile-completeness";
import type {
  AvailabilityStatus,
  CandidateProfileInput,
  ExperienceLevel,
  PreferredWorkType,
  PrivacyVisibility,
} from "@/lib/types";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  fieldInputClass,
} from "@/components/site/form";

const defaults: CandidateProfileInput = {
  headline: "",
  phone: "",
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
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border pt-8 first:border-t-0 first:pt-0">
      <h2 className="display-headline text-xl">{title}</h2>
      <div className="mt-6 space-y-5">{children}</div>
    </section>
  );
}

export function CandidateProfileEditForm({
  initialData,
}: {
  initialData: Partial<CandidateProfileInput>;
}) {
  const router = useRouter();
  const [form, setForm] = useState<CandidateProfileInput>({
    ...defaults,
    ...initialData,
  });
  const [status, setStatus] = useState<"idle" | "loading" | "uploading">("idle");
  const [error, setError] = useState("");
  const [resumeFileName, setResumeFileName] = useState(
    initialData.resumeUrl ? "Resume on file" : "",
  );

  const completeness = useMemo(
    () => calculateProfileCompleteness(form),
    [form],
  );

  function toggleCategory(category: string) {
    setForm((prev) => ({
      ...prev,
      roleCategories: prev.roleCategories.includes(category)
        ? prev.roleCategories.filter((c) => c !== category)
        : [...prev.roleCategories, category],
    }));
  }

  async function uploadResume(file: File) {
    setStatus("uploading");
    setError("");
    const body = new FormData();
    body.append("file", file);

    const response = await fetch("/api/candidate/resume", {
      method: "POST",
      body,
    });
    const data = await response.json();

    if (!response.ok) {
      setStatus("idle");
      throw new Error(data.error ?? "Resume upload failed");
    }

    setForm((prev) => ({ ...prev, resumeUrl: data.url }));
    setResumeFileName(file.name);
    setStatus("idle");
  }

  async function handleSubmit() {
    setStatus("loading");
    setError("");

    if (!form.headline.trim()) {
      setError("Add a professional headline.");
      setStatus("idle");
      return;
    }
    if (!form.skills.trim()) {
      setError("Add at least one skill.");
      setStatus("idle");
      return;
    }
    if (form.roleCategories.length === 0) {
      setError("Select at least one role category.");
      setStatus("idle");
      return;
    }
    if (!form.resumeUrl?.trim()) {
      setError("Upload your resume to keep your profile active.");
      setStatus("idle");
      return;
    }

    try {
      const response = await fetch("/api/candidate/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error ?? "Failed to save profile");
      }
      router.push("/candidate");
      router.refresh();
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <form autoComplete="off" onSubmit={(e) => e.preventDefault()}>
      <div className="mb-8 flex items-center justify-between gap-4 rounded-2xl border border-border bg-muted/40 px-5 py-4">
        <p className="text-sm text-muted-foreground">Profile completeness</p>
        <p className="font-mono text-sm text-primary">{completeness}%</p>
      </div>

      <Section title="Personal">
        <div>
          <FieldLabel htmlFor="headline">Professional headline</FieldLabel>
          <input
            id="headline"
            name="ps-professional-headline"
            autoComplete="off"
            className={fieldInputClass}
            value={form.headline}
            onChange={(e) => setForm({ ...form, headline: e.target.value })}
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="phone">Phone</FieldLabel>
            <input
              id="phone"
              type="tel"
              className={fieldInputClass}
              value={form.phone ?? ""}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="usState">US location</FieldLabel>
            <select
              id="usState"
              className={fieldInputClass}
              value={form.usState}
              onChange={(e) => setForm({ ...form, usState: e.target.value })}
            >
              {US_STATES.map((state) => (
                <option key={state} value={state}>
                  {state}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Section>

      <Section title="Work history">
        <div>
          <FieldLabel htmlFor="currentTitle">Current / recent title</FieldLabel>
          <input
            id="currentTitle"
            className={fieldInputClass}
            value={form.currentTitle ?? ""}
            onChange={(e) =>
              setForm({ ...form, currentTitle: e.target.value })
            }
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="yearsExperience">Years of experience</FieldLabel>
            <input
              id="yearsExperience"
              type="number"
              min={0}
              className={fieldInputClass}
              value={form.yearsExperience ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  yearsExperience: e.target.value
                    ? Number(e.target.value)
                    : undefined,
                })
              }
            />
          </div>
          <div>
            <FieldLabel htmlFor="experienceLevel">Seniority level</FieldLabel>
            <select
              id="experienceLevel"
              className={fieldInputClass}
              value={form.experienceLevel}
              onChange={(e) =>
                setForm({
                  ...form,
                  experienceLevel: e.target.value as ExperienceLevel,
                })
              }
            >
              {EXPERIENCE_LEVELS.map((level) => (
                <option key={level.value} value={level.value}>
                  {level.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <FieldLabel htmlFor="bio">Short bio</FieldLabel>
          <textarea
            id="bio"
            rows={3}
            className={fieldInputClass}
            value={form.bio ?? ""}
            onChange={(e) => setForm({ ...form, bio: e.target.value })}
          />
        </div>
      </Section>

      <Section title="Skills">
        <div>
          <FieldLabel>Role categories</FieldLabel>
          <div className="flex flex-wrap gap-2">
            {ROLE_CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => toggleCategory(category)}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  form.roleCategories.includes(category)
                    ? "bg-primary text-primary-foreground"
                    : "border border-border text-muted-foreground hover:border-primary/50"
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
        <div>
          <FieldLabel htmlFor="skills">Skills (comma-separated)</FieldLabel>
          <textarea
            id="skills"
            rows={3}
            className={fieldInputClass}
            value={form.skills}
            onChange={(e) => setForm({ ...form, skills: e.target.value })}
          />
        </div>
      </Section>

      <Section title="Preferences">
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="workAuthorization">Work authorization</FieldLabel>
            <p className="mb-2 text-sm text-muted-foreground">
              US-based roles need US work authorization. Remote contractors outside
              the US should choose the international option.
            </p>
            <select
              id="workAuthorization"
              className={fieldInputClass}
              value={form.workAuthorization}
              onChange={(e) =>
                setForm({ ...form, workAuthorization: e.target.value })
              }
            >
              {WORK_AUTH_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
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
              onChange={(e) =>
                setForm({
                  ...form,
                  preferredWorkType: e.target.value as PreferredWorkType,
                })
              }
            >
              {WORK_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="salaryMin">Salary range (USD)</FieldLabel>
            <div className="flex gap-3">
              <input
                type="number"
                className={fieldInputClass}
                placeholder="Min"
                value={form.salaryMin ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    salaryMin: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  })
                }
              />
              <input
                type="number"
                className={fieldInputClass}
                placeholder="Max"
                value={form.salaryMax ?? ""}
                onChange={(e) =>
                  setForm({
                    ...form,
                    salaryMax: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  })
                }
              />
            </div>
          </div>
          <div>
            <FieldLabel htmlFor="availabilityStatus">Availability</FieldLabel>
            <select
              id="availabilityStatus"
              className={fieldInputClass}
              value={form.availabilityStatus}
              onChange={(e) =>
                setForm({
                  ...form,
                  availabilityStatus: e.target.value as AvailabilityStatus,
                })
              }
            >
              {AVAILABILITY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <FieldLabel htmlFor="privacyVisibility">Profile visibility</FieldLabel>
          <select
            id="privacyVisibility"
            className={fieldInputClass}
            value={form.privacyVisibility}
            onChange={(e) =>
              setForm({
                ...form,
                privacyVisibility: e.target.value as PrivacyVisibility,
              })
            }
          >
            {PRIVACY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </Section>

      <Section title="Resume & links">
        <div>
          <FieldLabel htmlFor="resume">
            Resume <span className="text-primary">*</span>
          </FieldLabel>
          <label className="mt-2 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/40 px-6 py-8 transition-colors hover:border-primary/50">
            <Upload className="h-7 w-7 text-muted-foreground" />
            <span className="mt-2 text-sm font-medium">
              {resumeFileName || "Click to replace resume"}
            </span>
            <input
              id="resume"
              type="file"
              accept=".pdf,.doc,.docx"
              className="sr-only"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  await uploadResume(file);
                } catch (err) {
                  setError(
                    err instanceof Error ? err.message : "Upload failed",
                  );
                }
              }}
            />
          </label>
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <FieldLabel htmlFor="githubUrl">GitHub</FieldLabel>
            <input
              id="githubUrl"
              type="url"
              className={fieldInputClass}
              value={form.githubUrl ?? ""}
              onChange={(e) => setForm({ ...form, githubUrl: e.target.value })}
            />
          </div>
          <div>
            <FieldLabel htmlFor="portfolioUrl">Portfolio</FieldLabel>
            <input
              id="portfolioUrl"
              type="url"
              className={fieldInputClass}
              value={form.portfolioUrl ?? ""}
              onChange={(e) =>
                setForm({ ...form, portfolioUrl: e.target.value })
              }
            />
          </div>
        </div>
        <div>
          <FieldLabel htmlFor="linkedinUrl">LinkedIn</FieldLabel>
          <input
            id="linkedinUrl"
            type="url"
            className={fieldInputClass}
            value={form.linkedinUrl ?? ""}
            onChange={(e) =>
              setForm({ ...form, linkedinUrl: e.target.value })
            }
          />
        </div>
      </Section>

      {error && (
        <div className="mt-6">
          <ErrorBanner message={error} />
        </div>
      )}

      <div className="mt-8 flex justify-end border-t border-border pt-8">
        <PrimaryButton
          type="button"
          onClick={handleSubmit}
          disabled={status === "loading" || status === "uploading"}
        >
          {status === "loading"
            ? "Saving..."
            : status === "uploading"
              ? "Uploading..."
              : "Save changes"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </div>
    </form>
  );
}
