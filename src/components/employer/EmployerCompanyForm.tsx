"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Upload } from "lucide-react";
import { INDUSTRIES } from "@/lib/constants";
import type { CompanyInput } from "@/lib/types";
import {
  ErrorBanner,
  FieldLabel,
  PrimaryButton,
  fieldInputClass,
} from "@/components/site/form";

const defaults: CompanyInput = {
  name: "",
  website: "",
  size: "",
  description: "",
  hqCity: "",
  industry: "",
  remoteCultureStatement: "",
  logoUrl: "",
};

export function EmployerCompanyForm({
  initialData,
  workEmail,
  redirectTo = "/employer",
}: {
  initialData?: Partial<CompanyInput>;
  workEmail: string;
  redirectTo?: string;
}) {
  const router = useRouter();
  const [form, setForm] = useState<CompanyInput>({ ...defaults, ...initialData });
  const [status, setStatus] = useState<"idle" | "loading" | "uploading">("idle");
  const [error, setError] = useState("");

  async function uploadLogo(file: File) {
    setStatus("uploading");
    const body = new FormData();
    body.append("file", file);
    const response = await fetch("/api/employer/logo", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) {
      setStatus("idle");
      throw new Error(data.error ?? "Logo upload failed");
    }
    setForm((prev) => ({ ...prev, logoUrl: data.url }));
    setStatus("idle");
  }

  async function handleSubmit() {
    setStatus("loading");
    setError("");

    if (!form.description?.trim() || !form.hqCity?.trim() || !form.industry) {
      setError("Complete description, HQ city, and industry.");
      setStatus("idle");
      return;
    }

    try {
      const response = await fetch("/api/employer/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, workEmail }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Failed to save company");
      router.push(redirectTo);
      router.refresh();
    } catch (err) {
      setStatus("idle");
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <FieldLabel htmlFor="name">Company name</FieldLabel>
        <input
          id="name"
          required
          className={fieldInputClass}
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <FieldLabel htmlFor="website">Company website</FieldLabel>
          <input
            id="website"
            type="url"
            className={fieldInputClass}
            placeholder="https://company.com"
            value={form.website ?? ""}
            onChange={(e) => setForm({ ...form, website: e.target.value })}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Work email domain ({workEmail.split("@")[1]}) is verified against this
            website when they match.
          </p>
        </div>
        <div>
          <FieldLabel htmlFor="size">Company size</FieldLabel>
          <select
            id="size"
            required
            className={fieldInputClass}
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
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <FieldLabel htmlFor="hqCity">HQ city (US)</FieldLabel>
          <input
            id="hqCity"
            required
            className={fieldInputClass}
            placeholder="San Francisco, CA"
            value={form.hqCity ?? ""}
            onChange={(e) => setForm({ ...form, hqCity: e.target.value })}
          />
        </div>
        <div>
          <FieldLabel htmlFor="industry">Industry</FieldLabel>
          <select
            id="industry"
            required
            className={fieldInputClass}
            value={form.industry ?? ""}
            onChange={(e) => setForm({ ...form, industry: e.target.value })}
          >
            <option value="">Select</option>
            {INDUSTRIES.map((ind) => (
              <option key={ind} value={ind}>
                {ind}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <FieldLabel htmlFor="description">Company description</FieldLabel>
        <textarea
          id="description"
          required
          rows={4}
          className={fieldInputClass}
          value={form.description ?? ""}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>

      <div>
        <FieldLabel htmlFor="remoteCulture">Remote culture statement</FieldLabel>
        <textarea
          id="remoteCulture"
          rows={3}
          className={fieldInputClass}
          placeholder="How your team works remotely across the US..."
          value={form.remoteCultureStatement ?? ""}
          onChange={(e) =>
            setForm({ ...form, remoteCultureStatement: e.target.value })
          }
        />
      </div>

      <div>
        <FieldLabel>Company logo</FieldLabel>
        <label className="mt-2 flex cursor-pointer items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-muted/40 px-6 py-8 transition-colors hover:border-primary/50">
          <Upload className="h-6 w-6 text-muted-foreground" />
          <span className="text-sm font-medium">
            {form.logoUrl ? "Logo uploaded — click to replace" : "Upload logo"}
          </span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/svg+xml"
            className="sr-only"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                await uploadLogo(file);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Upload failed");
              }
            }}
          />
        </label>
      </div>

      {error && <ErrorBanner message={error} />}

      <PrimaryButton
        type="button"
        onClick={handleSubmit}
        disabled={status === "loading" || status === "uploading"}
        className="w-full sm:w-auto"
      >
        {status === "loading" ? "Saving..." : "Save company"}
        <ArrowRight className="h-4 w-4" />
      </PrimaryButton>
    </div>
  );
}
