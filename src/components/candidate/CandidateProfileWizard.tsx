"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Upload } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
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
  SecondaryButton,
  fieldInputClass,
} from "@/components/site/form";

const STEPS = [
  { id: "personal", label: "Personal info", code: "01" },
  { id: "work", label: "Work history", code: "02" },
  { id: "skills", label: "Skills", code: "03" },
  { id: "preferences", label: "Preferences", code: "04" },
  { id: "verification", label: "Verification", code: "05" },
] as const;

const initial: CandidateProfileInput = {
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

export function CandidateProfileWizard({
  initialData,
  redirectTo = "/candidate",
}: {
  initialData?: Partial<CandidateProfileInput>;
  redirectTo?: string;
}) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<CandidateProfileInput>({
    ...initial,
    ...initialData,
  });
  const [status, setStatus] = useState<"idle" | "loading" | "uploading">(
    "idle",
  );
  const [error, setError] = useState("");
  const [resumeFileName, setResumeFileName] = useState(
    initialData?.resumeUrl ? "Resume on file" : "",
  );

  const completeness = useMemo(
    () => calculateProfileCompleteness(form),
    [form],
  );

  const wizardProgress = useMemo(() => {
    const checks = [
      Boolean(form.headline.trim()),
      Boolean(form.phone?.trim()),
      step > 0 || form.usState !== initial.usState,
      Boolean(form.currentTitle?.trim()),
      form.yearsExperience !== undefined && form.yearsExperience >= 0,
      Boolean(form.bio?.trim()),
      (form.roleCategories?.length ?? 0) > 0,
      Boolean(form.skills.trim()),
      step > 1 || form.experienceLevel !== initial.experienceLevel,
      step > 3 || form.workAuthorization !== initial.workAuthorization,
      step > 3 || form.preferredWorkType !== initial.preferredWorkType,
      step > 3 || form.availabilityStatus !== initial.availabilityStatus,
      step > 3 || form.privacyVisibility !== initial.privacyVisibility,
      form.salaryMin !== undefined || form.salaryMax !== undefined,
      Boolean(form.resumeUrl),
      Boolean(
        form.githubUrl?.trim() ||
          form.portfolioUrl?.trim() ||
          form.linkedinUrl?.trim(),
      ),
    ];

    return Math.round(
      (checks.filter(Boolean).length / checks.length) * 100,
    );
  }, [form, step]);

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

  function validateStep(): string | null {
    if (step === 0) {
      if (!form.headline.trim()) return "Add a professional headline.";
      if (!form.phone?.trim()) return "Add a phone number.";
      return null;
    }
    if (step === 1) {
      if (!form.currentTitle?.trim()) return "Add your current or recent title.";
      return null;
    }
    if (step === 2) {
      if (!form.skills.trim()) return "Add at least one skill.";
      if (form.roleCategories.length === 0)
        return "Select at least one role category.";
      return null;
    }
    if (step === 4) {
      if (!form.resumeUrl?.trim()) {
        return "Upload your resume (PDF or DOCX) to finish your profile.";
      }
      return null;
    }
    return null;
  }

  async function handleFinish() {
    setStatus("loading");
    setError("");

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
      router.push(redirectTo);
      router.refresh();
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  function nextStep() {
    const validationError = validateStep();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError("");
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
      return;
    }
    handleFinish();
  }

  return (
    <form autoComplete="off" onSubmit={(e) => e.preventDefault()}>
      <div className="mb-8">
        <div className="flex items-center justify-between gap-4">
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">
            Profile builder · Step {STEPS[step].code}
          </p>
          <p className="font-mono text-xs text-primary">
            {wizardProgress}% complete
          </p>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="h-full bg-primary"
            animate={{ width: `${wizardProgress}%` }}
            transition={{ duration: 0.4 }}
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {STEPS.map((s, i) => (
            <span
              key={s.id}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                i === step
                  ? "bg-primary text-primary-foreground"
                  : i < step
                    ? "bg-muted text-foreground"
                    : "border border-border text-muted-foreground"
              }`}
            >
              {s.label}
            </span>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
          transition={{ duration: 0.3 }}
          className="space-y-6"
        >
          {step === 0 && (
            <>
              <h3 className="display-headline text-3xl">Personal info</h3>
              <div>
                <FieldLabel htmlFor="headline">Professional headline</FieldLabel>
                <input
                  id="headline"
                  name="ps-professional-headline"
                  autoComplete="off"
                  className={fieldInputClass}
                  placeholder="Your role and top skills"
                  value={form.headline}
                  onChange={(e) =>
                    setForm({ ...form, headline: e.target.value })
                  }
                />
              </div>
              <div>
                <FieldLabel htmlFor="phone">Phone</FieldLabel>
                <input
                  id="phone"
                  name="ps-phone"
                  type="tel"
                  autoComplete="off"
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
            </>
          )}

          {step === 1 && (
            <>
              <h3 className="display-headline text-3xl">Work history</h3>
              <div>
                <FieldLabel htmlFor="currentTitle">Current / recent title</FieldLabel>
                <input
                  id="currentTitle"
                  name="ps-current-title"
                  autoComplete="off"
                  className={fieldInputClass}
                  placeholder="Your current or recent job title"
                  value={form.currentTitle ?? ""}
                  onChange={(e) =>
                    setForm({ ...form, currentTitle: e.target.value })
                  }
                />
              </div>
              <div className="grid gap-6 sm:grid-cols-2">
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
                  name="ps-bio"
                  autoComplete="off"
                  rows={4}
                  className={fieldInputClass}
                  placeholder="Share the kind of work you do best and what makes you a strong fit."
                  value={form.bio ?? ""}
                  onChange={(e) => setForm({ ...form, bio: e.target.value })}
                />
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h3 className="display-headline text-3xl">Skills</h3>
              <div>
                <FieldLabel>Role categories (US tech)</FieldLabel>
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
                  name="ps-skills"
                  autoComplete="off"
                  rows={4}
                  className={fieldInputClass}
                  placeholder="List your skills, separated by commas"
                  value={form.skills}
                  onChange={(e) => setForm({ ...form, skills: e.target.value })}
                />
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h3 className="display-headline text-3xl">Preferences</h3>
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <FieldLabel htmlFor="workAuthorization">
                    Work authorization
                  </FieldLabel>
                  <p className="mb-2 text-sm text-muted-foreground">
                    US-based roles need US work authorization. Remote contractors
                    outside the US should choose the international option.
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
                  <FieldLabel htmlFor="preferredWorkType">Preferred work type</FieldLabel>
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
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <FieldLabel htmlFor="salaryMin">Salary range (USD)</FieldLabel>
                  <div className="flex gap-3">
                    <input
                      id="salaryMin"
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
            </>
          )}

          {step === 4 && (
            <>
              <h3 className="display-headline text-3xl">Verification</h3>
              <p className="text-sm text-muted-foreground">
                Resume upload is required to activate matching.
              </p>
              <div>
                <FieldLabel htmlFor="resume">
                  Resume (PDF or DOCX) <span className="text-primary">*</span>
                </FieldLabel>
                <label className="mt-2 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/40 px-6 py-10 transition-colors hover:border-primary/50 hover:bg-muted/60">
                  <Upload className="h-8 w-8 text-muted-foreground" />
                  <span className="mt-3 text-sm font-medium">
                    {resumeFileName || form.resumeUrl
                      ? resumeFileName || "Resume uploaded"
                      : "Click to upload resume"}
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
              <div className="grid gap-6 sm:grid-cols-2">
                <div>
                  <FieldLabel htmlFor="githubUrl">GitHub</FieldLabel>
                  <input
                    id="githubUrl"
                    type="url"
                    className={fieldInputClass}
                    placeholder="https://github.com/you"
                    value={form.githubUrl ?? ""}
                    onChange={(e) =>
                      setForm({ ...form, githubUrl: e.target.value })
                    }
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="portfolioUrl">Portfolio / website</FieldLabel>
                  <input
                    id="portfolioUrl"
                    type="url"
                    className={fieldInputClass}
                    placeholder="https://"
                    value={form.portfolioUrl ?? ""}
                    onChange={(e) =>
                      setForm({ ...form, portfolioUrl: e.target.value })
                    }
                  />
                </div>
              </div>
              <div>
                <FieldLabel htmlFor="linkedinUrl">LinkedIn profile</FieldLabel>
                <input
                  id="linkedinUrl"
                  type="url"
                  className={fieldInputClass}
                  placeholder="https://linkedin.com/in/you"
                  value={form.linkedinUrl ?? ""}
                  onChange={(e) =>
                    setForm({ ...form, linkedinUrl: e.target.value })
                  }
                />
              </div>
            </>
          )}
        </motion.div>
      </AnimatePresence>

      {error && <div className="mt-6"><ErrorBanner message={error} /></div>}

      <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:items-center">
        {step > 0 && (
          <SecondaryButton
            type="button"
            onClick={() => {
              setError("");
              setStep((s) => s - 1);
            }}
            className="w-full sm:w-auto"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </SecondaryButton>
        )}
        <PrimaryButton
          type="button"
          onClick={nextStep}
          disabled={status === "loading" || status === "uploading"}
          className="w-full sm:ml-auto sm:w-auto"
        >
          {status === "loading"
            ? "Saving..."
            : status === "uploading"
              ? "Uploading..."
              : step === STEPS.length - 1
                ? "Save and get matched"
                : "Continue"}
          <ArrowRight className="h-4 w-4" />
        </PrimaryButton>
      </div>
    </form>
  );
}
