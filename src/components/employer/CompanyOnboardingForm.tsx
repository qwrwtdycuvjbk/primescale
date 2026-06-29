"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { CompanyInput } from "@/lib/types";
import { buttonPrimaryClass, inputClass, labelClass } from "@/lib/ui";

export function CompanyOnboardingForm() {
  const router = useRouter();
  const [form, setForm] = useState<CompanyInput>({
    name: "",
    website: "",
    size: "",
  });
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setStatus("loading");
    setError("");

    try {
      const response = await fetch("/api/employer/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error ?? "Failed to save company");
      }

      router.push("/employer/jobs/new");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="name" className={labelClass}>
          Company name
        </label>
        <input
          id="name"
          required
          className={inputClass}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </div>

      <div>
        <label htmlFor="website" className={labelClass}>
          Company website
        </label>
        <input
          id="website"
          type="url"
          className={inputClass}
          placeholder="https://"
          value={form.website ?? ""}
          onChange={(e) => setForm({ ...form, website: e.target.value })}
        />
      </div>

      <div>
        <label htmlFor="size" className={labelClass}>
          Company size
        </label>
        <select
          id="size"
          className={inputClass}
          value={form.size ?? ""}
          onChange={(e) => setForm({ ...form, size: e.target.value })}
        >
          <option value="">Select</option>
          <option value="1-10">1–10</option>
          <option value="11-50">11–50</option>
          <option value="51-200">51–200</option>
          <option value="201-500">201–500</option>
          <option value="500+">500+</option>
        </select>
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
        {status === "loading" ? "Saving..." : "Continue to post a role"}
      </button>
    </form>
  );
}
