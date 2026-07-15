"use client";

import { useMemo, useState } from "react";
import { JobPostForm } from "@/components/employer/JobPostForm";
import { FieldLabel, fieldInputClass } from "@/components/site/form";

type CompanyOption = {
  id: string;
  name: string;
};

export function AdminJobPostForm({
  companies,
}: {
  companies: CompanyOption[];
}) {
  const defaultCompanyId =
    companies.find((company) =>
      company.name.toLowerCase().includes("people prime"),
    )?.id ??
    companies[0]?.id ??
    "";
  const [companyId, setCompanyId] = useState(defaultCompanyId);
  const company = useMemo(
    () => companies.find((option) => option.id === companyId),
    [companies, companyId],
  );

  if (!company) {
    return (
      <p className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
        No company profile is available. Create the People Prime company profile
        before adding a job.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <FieldLabel htmlFor="company">Post for company</FieldLabel>
        <select
          id="company"
          className={fieldInputClass}
          value={companyId}
          onChange={(event) => setCompanyId(event.target.value)}
        >
          {companies.map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </select>
      </div>

      <JobPostForm
        key={company.id}
        companyName={company.name}
        companyId={company.id}
        submitEndpoint="/api/admin/jobs"
        redirectTo="/admin/jobs"
      />
    </div>
  );
}
