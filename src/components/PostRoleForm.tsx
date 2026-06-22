"use client";

import { useState, type FormEvent } from "react";
import type {
  ExperienceLevel,
  RoleSubmissionInput,
  RoleType,
} from "@/lib/types";

const initialForm: RoleSubmissionInput = {
  companyName: "",
  contactName: "",
  email: "",
  jobTitle: "",
  roleType: "contract",
  experienceLevel: "mid",
  techStack: "",
  salaryRange: "",
  description: "",
  notes: "",
};

type FormStatus = "idle" | "submitting" | "success" | "error";

export function PostRoleForm() {
  const [form, setForm] = useState<RoleSubmissionInput>(initialForm);
  const [pastedJobDescription, setPastedJobDescription] = useState("");
  const [showDetailedForm, setShowDetailedForm] = useState(false);
  const [status, setStatus] = useState<FormStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [submittedEmail, setSubmittedEmail] = useState("");

  function updateField<K extends keyof RoleSubmissionInput>(
    field: K,
    value: RoleSubmissionInput[K],
  ) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("submitting");
    setErrorMessage("");

    const description =
      pastedJobDescription.trim() || form.description.trim();
    const usingPastedJd = pastedJobDescription.trim().length > 0;

    if (!description) {
      setStatus("error");
      setErrorMessage(
        "Please paste your job description or fill out the role details below.",
      );
      return;
    }

    if (showDetailedForm && !usingPastedJd) {
      if (!form.jobTitle.trim() || !form.techStack.trim()) {
        setStatus("error");
        setErrorMessage("Please fill in the job title and tech stack.");
        return;
      }
    }

    const payload: RoleSubmissionInput = {
      ...form,
      description,
      jobTitle: form.jobTitle.trim() || "See pasted job description",
      techStack: form.techStack.trim() || "See pasted job description",
      submissionType: usingPastedJd ? "pasted_jd" : "manual_form",
    };

    try {
      const response = await fetch("/api/roles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Something went wrong");
      }

      setSubmittedEmail(form.email);
      setStatus("success");
      setForm(initialForm);
      setPastedJobDescription("");
      setShowDetailedForm(false);
    } catch (error) {
      setStatus("error");
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to submit role",
      );
    }
  }

  if (status === "success") {
    return (
      <div className="rounded-2xl border border-teal-200 bg-teal-50 p-10 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal-500 text-2xl text-white">
          ✓
        </div>
        <h3 className="mt-6 text-2xl font-bold text-slate-900">
          Role received. We&apos;re on it.
        </h3>
        <p className="mx-auto mt-3 max-w-md text-slate-600">
          The People Prime team will review your requirements and send vetted
          candidate profiles within 24 hours to{" "}
          <span className="font-medium text-slate-900">{submittedEmail}</span>.
        </p>
        <button
          type="button"
          onClick={() => setStatus("idle")}
          className="mt-8 text-sm font-semibold text-teal-700 hover:text-teal-800"
        >
          Post another role
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <Field label="Company name" required>
          <input
            type="text"
            required
            value={form.companyName}
            onChange={(e) => updateField("companyName", e.target.value)}
            placeholder="Acme Inc."
            className={inputClass}
          />
        </Field>

        <Field label="Your name" required>
          <input
            type="text"
            required
            value={form.contactName}
            onChange={(e) => updateField("contactName", e.target.value)}
            placeholder="Jane Smith"
            className={inputClass}
          />
        </Field>
      </div>

      <Field label="Work email" required>
        <input
          type="email"
          required
          value={form.email}
          onChange={(e) => updateField("email", e.target.value)}
          placeholder="jane@acme.com"
          className={inputClass}
        />
      </Field>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-600">
            <DocumentIcon />
          </span>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              Have a JD already?
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              Paste it below and we&apos;ll pull out the key details
              automatically.
            </p>
          </div>
        </div>

        <textarea
          rows={8}
          value={pastedJobDescription}
          onChange={(e) => setPastedJobDescription(e.target.value)}
          placeholder="Paste your job description here. Role, tech stack, experience level, anything you've got. We'll handle the rest."
          className="mt-5 min-h-[200px] w-full resize-y rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-teal-500 focus:bg-white focus:ring-2 focus:ring-teal-500/20"
        />
      </div>

      <div className="flex items-center gap-4">
        <div className="h-px flex-1 bg-slate-200" />
        <span className="text-sm font-medium text-slate-500">or</span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>

      <button
        type="button"
        onClick={() => setShowDetailedForm((open) => !open)}
        className="flex w-full items-center justify-center gap-2 text-sm font-medium text-teal-600 transition hover:text-teal-700"
      >
        <ChevronIcon open={showDetailedForm} />
        {showDetailedForm
          ? "Hide the quick form"
          : "Don't have one ready? Fill out a quick form instead"}
      </button>

      {showDetailedForm && (
        <div className="space-y-6 rounded-2xl border border-slate-200 bg-slate-50 p-6">
          <Field label="Job title" required>
            <input
              type="text"
              value={form.jobTitle}
              onChange={(e) => updateField("jobTitle", e.target.value)}
              placeholder="Senior Full-Stack Engineer"
              className={inputClass}
            />
          </Field>

          <div className="grid gap-6 sm:grid-cols-2">
            <Field label="Role type" required>
              <select
                value={form.roleType}
                onChange={(e) =>
                  updateField("roleType", e.target.value as RoleType)
                }
                className={inputClass}
              >
                <option value="contract">Contract</option>
                <option value="c2h">C2H (Contract to Hire)</option>
                <option value="full-time">Full-time</option>
              </select>
            </Field>

            <Field label="Experience level" required>
              <select
                value={form.experienceLevel}
                onChange={(e) =>
                  updateField(
                    "experienceLevel",
                    e.target.value as ExperienceLevel,
                  )
                }
                className={inputClass}
              >
                <option value="junior">Junior (0-2 yrs)</option>
                <option value="mid">Mid-level (3-5 yrs)</option>
                <option value="senior">Senior (5+ yrs)</option>
                <option value="lead">Lead / Staff</option>
              </select>
            </Field>
          </div>

          <Field label="Tech stack / skills" required>
            <input
              type="text"
              value={form.techStack}
              onChange={(e) => updateField("techStack", e.target.value)}
              placeholder="React, Node.js, PostgreSQL, AWS"
              className={inputClass}
            />
          </Field>

          <Field label="Salary range (optional)">
            <input
              type="text"
              value={form.salaryRange}
              onChange={(e) => updateField("salaryRange", e.target.value)}
              placeholder="$120k to $160k USD"
              className={inputClass}
            />
          </Field>

          <Field label="Role description">
            <textarea
              rows={5}
              value={form.description}
              onChange={(e) => updateField("description", e.target.value)}
              placeholder="What will this person build? What does your team look like? Any must-have experience?"
              className={inputClass}
            />
          </Field>

          <Field label="Additional notes (optional)">
            <textarea
              rows={3}
              value={form.notes}
              onChange={(e) => updateField("notes", e.target.value)}
              placeholder="Timezone preferences, start date, interview process, etc."
              className={inputClass}
            />
          </Field>
        </div>
      )}

      {status === "error" && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="w-full rounded-full bg-teal-500 py-4 text-base font-semibold text-slate-950 transition hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {status === "submitting"
          ? "Submitting..."
          : "Submit role and get candidates in 24h"}
      </button>
    </form>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
        {required && <span className="text-teal-600"> *</span>}
      </span>
      {children}
    </label>
  );
}

function DocumentIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      className="h-5 w-5"
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`}
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

const inputClass =
  "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20";
