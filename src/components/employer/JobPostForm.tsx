"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { EXPERIENCE_LEVELS, ROLE_TYPES } from "@/lib/constants";
import type { ExperienceLevel, JobInput, RoleType } from "@/lib/types";
import { buttonPrimaryClass, inputClass, labelClass } from "@/lib/ui";

const initial: JobInput = {
  title: "",
  description: "",
  roleType: "contract",
  experienceLevel: "mid",
  techStack: "",
  salaryRange: "",
  visaRequirements: "",
  pastedJd: "",
};

export function JobPostForm() {
  const router = useRouter();
  const [form, setForm] = useState<JobInput>(initial);
  const [pastedJd, setPastedJd] = useState("");
  const [useDetailed, setUseDetailed] = useState(false);
  const [status, setStatus] = useState<"idle" | "loading" | "parsing" | "error">(
    "idle",
  );
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
          experienceLevel:
            data.parsed.experience_level ?? prev.experienceLevel,
          roleType: data.parsed.role_type ?? prev.roleType,
          salaryRange: data.parsed.salary_range ?? prev.salaryRange,
        }));
        setUseDetailed(true);
      } else {
        setForm((prev) => ({ ...prev, description: pastedJd }));
        setUseDetailed(true);
      }
    } catch {
      setForm((prev) => ({ ...prev, description: pastedJd }));
      setUseDetailed(true);
    } finally {
      setStatus("idle");
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setError("");

    const description = form.description.trim() || pastedJd.trim();
    if (!description) {
      setStatus("error");
      setError("Add a job description or paste your JD.");
      return;
    }

    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, description, pastedJd }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error ?? "Failed to post job");
      }

      router.push("/employer");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="pastedJd" className={labelClass}>
          Paste job description (AI-assisted)
        </label>
        <textarea
          id="pastedJd"
          rows={6}
          className={inputClass}
          placeholder="Paste your full JD here..."
          value={pastedJd}
          onChange={(e) => setPastedJd(e.target.value)}
        />
        <button
          type="button"
          onClick={parseJd}
          disabled={status === "parsing" || !pastedJd.trim()}
          className="mt-3 text-sm font-medium text-teal-600 hover:text-teal-500"
        >
          {status === "parsing" ? "Parsing..." : "Parse with AI"}
        </button>
      </div>

      {!useDetailed && (
        <button
          type="button"
          onClick={() => setUseDetailed(true)}
          className="text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          Or fill in details manually
        </button>
      )}

      {useDetailed && (
        <>
          <div>
            <label htmlFor="title" className={labelClass}>
              Job title
            </label>
            <input
              id="title"
              required
              className={inputClass}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>

          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="roleType" className={labelClass}>
                Engagement type
              </label>
              <select
                id="roleType"
                className={inputClass}
                value={form.roleType}
                onChange={(e) =>
                  setForm({ ...form, roleType: e.target.value as RoleType })
                }
              >
                {ROLE_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="experienceLevel" className={labelClass}>
                Experience level
              </label>
              <select
                id="experienceLevel"
                className={inputClass}
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
            <label htmlFor="techStack" className={labelClass}>
              Tech stack (comma-separated)
            </label>
            <input
              id="techStack"
              required
              className={inputClass}
              value={form.techStack}
              onChange={(e) => setForm({ ...form, techStack: e.target.value })}
            />
          </div>

          <div>
            <label htmlFor="salaryRange" className={labelClass}>
              Salary range (optional)
            </label>
            <input
              id="salaryRange"
              className={inputClass}
              placeholder="$120k–$160k"
              value={form.salaryRange ?? ""}
              onChange={(e) =>
                setForm({ ...form, salaryRange: e.target.value })
              }
            />
          </div>

          <div>
            <label htmlFor="description" className={labelClass}>
              Role description
            </label>
            <textarea
              id="description"
              required
              rows={5}
              className={inputClass}
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
          </div>

          <div>
            <label htmlFor="visaRequirements" className={labelClass}>
              Visa / work authorization requirements
            </label>
            <input
              id="visaRequirements"
              className={inputClass}
              placeholder="US citizens and green card holders only"
              value={form.visaRequirements ?? ""}
              onChange={(e) =>
                setForm({ ...form, visaRequirements: e.target.value })
              }
            />
          </div>
        </>
      )}

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "loading" || status === "parsing"}
        className={buttonPrimaryClass}
      >
        {status === "loading" ? "Posting..." : "Post role and find matches"}
      </button>
    </form>
  );
}
