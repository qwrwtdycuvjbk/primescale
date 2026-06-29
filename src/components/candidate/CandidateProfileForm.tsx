"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  EXPERIENCE_LEVELS,
  ROLE_CATEGORIES,
  US_STATES,
  WORK_AUTH_OPTIONS,
} from "@/lib/constants";
import type { CandidateProfileInput, ExperienceLevel } from "@/lib/types";
import { buttonPrimaryClass, inputClass, labelClass } from "@/lib/ui";

const initial: CandidateProfileInput = {
  headline: "",
  skills: "",
  roleCategories: [],
  experienceLevel: "mid",
  workAuthorization: "us_citizen",
  usState: "Remote (US)",
  bio: "",
};

export function CandidateProfileForm({
  initialData,
}: {
  initialData?: Partial<CandidateProfileInput>;
}) {
  const router = useRouter();
  const [form, setForm] = useState<CandidateProfileInput>({
    ...initial,
    ...initialData,
  });
  const [status, setStatus] = useState<"idle" | "loading" | "error" | "success">(
    "idle",
  );
  const [error, setError] = useState("");

  function toggleCategory(category: string) {
    setForm((prev) => ({
      ...prev,
      roleCategories: prev.roleCategories.includes(category)
        ? prev.roleCategories.filter((c) => c !== category)
        : [...prev.roleCategories, category],
    }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setError("");

    if (form.roleCategories.length === 0) {
      setStatus("error");
      setError("Select at least one role category.");
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

      setStatus("success");
      router.push("/candidate");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="headline" className={labelClass}>
          Professional headline
        </label>
        <input
          id="headline"
          required
          className={inputClass}
          placeholder="Senior DevOps engineer, AWS & Kubernetes"
          value={form.headline}
          onChange={(e) => setForm({ ...form, headline: e.target.value })}
        />
      </div>

      <div>
        <label className={labelClass}>Role categories (US tech)</label>
        <div className="flex flex-wrap gap-2">
          {ROLE_CATEGORIES.map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => toggleCategory(category)}
              className={`rounded-full px-4 py-2 text-sm transition ${
                form.roleCategories.includes(category)
                  ? "bg-teal-500 text-slate-950"
                  : "border border-slate-200 text-slate-600 hover:border-teal-300"
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label htmlFor="skills" className={labelClass}>
          Skills (comma-separated)
        </label>
        <textarea
          id="skills"
          required
          rows={3}
          className={inputClass}
          placeholder="Python, AWS, Terraform, Kubernetes, CI/CD"
          value={form.skills}
          onChange={(e) => setForm({ ...form, skills: e.target.value })}
        />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
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

        <div>
          <label htmlFor="usState" className={labelClass}>
            US location
          </label>
          <select
            id="usState"
            className={inputClass}
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

      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <label htmlFor="workAuthorization" className={labelClass}>
            US work authorization
          </label>
          <select
            id="workAuthorization"
            className={inputClass}
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
          <label htmlFor="salaryMin" className={labelClass}>
            Salary range (USD, optional)
          </label>
          <div className="flex gap-3">
            <input
              id="salaryMin"
              type="number"
              className={inputClass}
              placeholder="Min"
              value={form.salaryMin ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  salaryMin: e.target.value ? Number(e.target.value) : undefined,
                })
              }
            />
            <input
              type="number"
              className={inputClass}
              placeholder="Max"
              value={form.salaryMax ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  salaryMax: e.target.value ? Number(e.target.value) : undefined,
                })
              }
            />
          </div>
        </div>
      </div>

      <div>
        <label htmlFor="bio" className={labelClass}>
          Short bio (optional)
        </label>
        <textarea
          id="bio"
          rows={4}
          className={inputClass}
          value={form.bio ?? ""}
          onChange={(e) => setForm({ ...form, bio: e.target.value })}
        />
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={status === "loading"}
        className={buttonPrimaryClass}
      >
        {status === "loading" ? "Saving..." : "Save profile and get matched"}
      </button>
    </form>
  );
}
