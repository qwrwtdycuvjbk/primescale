"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Eye } from "lucide-react";
import { EXPERIENCE_LEVELS, ROLE_TYPES } from "@/lib/constants";
import { isValidSalaryRange } from "@/lib/employer";
import { parseSkills } from "@/lib/matching";
import type { ExperienceLevel, JobInput, RoleType } from "@/lib/types";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  SecondaryButton,
  fieldInputClass,
} from "@/components/site/form";

const initial: JobInput = {
  title: "",
  description: "",
  roleType: "contract",
  experienceLevel: "mid",
  techStack: "",
  salaryRange: "",
  workType: "remote",
  visaRequirements: "",
};

export function JobPostForm({ companyName }: { companyName: string }) {
  const router = useRouter();
  const [form, setForm] = useState<JobInput>(initial);
  const [pastedJd, setPastedJd] = useState("");
  const [step, setStep] = useState<"edit" | "preview">("edit");
  const [status, setStatus] = useState<"idle" | "loading" | "parsing">("idle");
  const [error, setError] = useState("");

  async function parseJd() {
    if (!pastedJd.trim()) return;
    setStatus("parsing");
    setError("");
    try {
      const response = await fetch("/api/jobs/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pastedJd }),
      });
      const data = await response.json();
      if (data.parsed) {
        setForm((prev) => ({
          ...prev,
          title: data.parsed.title ?? prev.title,
          description: data.parsed.description ?? pastedJd,
          techStack: (data.parsed.tech_stack ?? []).join(", "),
          experienceLevel: data.parsed.experience_level ?? prev.experienceLevel,
          roleType: data.parsed.role_type ?? prev.roleType,
          salaryRange: data.parsed.salary_range ?? prev.salaryRange,
        }));
      } else {
        setForm((prev) => ({ ...prev, description: pastedJd }));
      }
    } catch {
      setForm((prev) => ({ ...prev, description: pastedJd }));
    } finally {
      setStatus("idle");
    }
  }

  function validate(): string | null {
    if (!form.title.trim()) return "Job title is required.";
    if (!form.description.trim() && !pastedJd.trim()) return "Job description is required.";
    const skills = parseSkills(form.techStack);
    if (skills.length < 3) return "Add at least 3 required skills.";
    if (!form.salaryRange.trim()) return "Salary range is required (no hidden pay).";
    if (!isValidSalaryRange(form.salaryRange)) {
      return 'Use a real salary range (e.g. "$120k–$160k"). "Competitive" is not allowed.';
    }
    if (!form.visaRequirements.trim()) {
      return "Describe who can work remotely in the US for this role.";
    }
    return null;
  }

  function goToPreview() {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError("");
    setStep("preview");
  }

  async function submit(publish: boolean) {
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setStatus("loading");
    setError("");
    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...form,
          description: form.description.trim() || pastedJd.trim(),
          publish,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Failed to save job");
      router.push("/employer/jobs");
      router.refresh();
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  if (step === "preview") {
    const skills = parseSkills(form.techStack);
    return (
      <div className="space-y-6">
        <button
          type="button"
          onClick={() => setStep("edit")}
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to edit
        </button>

        <div className="rounded-3xl border border-border bg-card p-8">
          <p className="text-sm text-muted-foreground">Candidate preview</p>
          <h2 className="display-headline mt-2 text-3xl">{form.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{companyName}</p>

          <div className="mt-6 flex flex-wrap gap-2">
            {skills.map((s) => (
              <span key={s} className="rounded-full border border-border px-3 py-1 text-xs">
                {s}
              </span>
            ))}
          </div>

          <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Salary</dt>
              <dd className="font-medium">{form.salaryRange}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Work type</dt>
              <dd className="font-medium capitalize">{form.workType}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-muted-foreground">Remote work eligibility</dt>
              <dd className="font-medium">{form.visaRequirements}</dd>
            </div>
          </dl>

          <div className="mt-6 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
            {form.description || pastedJd}
          </div>
        </div>

        {error && <ErrorBanner message={error} />}

        <div className="flex flex-wrap gap-3">
          <SecondaryButton type="button" onClick={() => submit(false)} disabled={status === "loading"}>
            Save as draft
          </SecondaryButton>
          <PrimaryButton type="button" onClick={() => submit(true)} disabled={status === "loading"}>
            {status === "loading" ? "Publishing..." : "Publish job"}
            <ArrowRight className="h-4 w-4" />
          </PrimaryButton>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <FieldLabel htmlFor="pastedJd">Paste job description (AI-assisted)</FieldLabel>
        <textarea
          id="pastedJd"
          rows={5}
          className={fieldInputClass}
          placeholder="Paste your full JD..."
          value={pastedJd}
          onChange={(e) => setPastedJd(e.target.value)}
        />
        <button
          type="button"
          onClick={parseJd}
          disabled={status === "parsing" || !pastedJd.trim()}
          className="mt-2 text-sm font-medium text-primary hover:opacity-80"
        >
          {status === "parsing" ? "Parsing..." : "Parse with AI"}
        </button>
      </div>

      <div>
        <FieldLabel htmlFor="title">Job title</FieldLabel>
        <input
          id="title"
          required
          className={fieldInputClass}
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <FieldLabel htmlFor="roleType">Engagement type</FieldLabel>
          <select
            id="roleType"
            className={fieldInputClass}
            value={form.roleType}
            onChange={(e) => setForm({ ...form, roleType: e.target.value as RoleType })}
          >
            {ROLE_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
        <div>
          <FieldLabel htmlFor="experienceLevel">Experience level</FieldLabel>
          <select
            id="experienceLevel"
            className={fieldInputClass}
            value={form.experienceLevel}
            onChange={(e) =>
              setForm({ ...form, experienceLevel: e.target.value as ExperienceLevel })
            }
          >
            {EXPERIENCE_LEVELS.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <FieldLabel htmlFor="techStack">Skills required (min. 3, comma-separated)</FieldLabel>
        <input
          id="techStack"
          required
          className={fieldInputClass}
          placeholder="Python, AWS, Kubernetes"
          value={form.techStack}
          onChange={(e) => setForm({ ...form, techStack: e.target.value })}
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <FieldLabel htmlFor="salaryRange">Salary range (required)</FieldLabel>
          <input
            id="salaryRange"
            required
            className={fieldInputClass}
            placeholder="$120,000–$160,000"
            value={form.salaryRange}
            onChange={(e) => setForm({ ...form, salaryRange: e.target.value })}
          />
        </div>
        <div>
          <FieldLabel htmlFor="workType">Work type</FieldLabel>
          <select
            id="workType"
            className={fieldInputClass}
            value={form.workType}
            onChange={(e) => setForm({ ...form, workType: e.target.value })}
          >
            <option value="remote">Remote (US)</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </select>
        </div>
      </div>

      <div>
        <FieldLabel htmlFor="description">Role description</FieldLabel>
        <textarea
          id="description"
          rows={6}
          className={fieldInputClass}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>

      <div>
        <FieldLabel htmlFor="visaRequirements">
          Who can work remotely in the US?
        </FieldLabel>
        <input
          id="visaRequirements"
          required
          className={fieldInputClass}
          placeholder="e.g. US citizens, green card holders, or TN visa — remote within US time zones"
          value={form.visaRequirements}
          onChange={(e) => setForm({ ...form, visaRequirements: e.target.value })}
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          PrimeScale is US remote only. Tell candidates which work authorizations you
          accept for this fully remote role.
        </p>
      </div>

      {error && <ErrorBanner message={error} />}

      <PrimaryButton type="button" onClick={goToPreview} disabled={status === "parsing"}>
        <Eye className="h-4 w-4" />
        Preview before publishing
      </PrimaryButton>
    </div>
  );
}
