"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, Upload } from "lucide-react";
import { CANDIDATE_IMPORT_TEMPLATE_PATH } from "@/lib/admin-candidate-csv";
import { ErrorBanner, PrimaryButton } from "@/components/site/form";

type ImportResult = {
  totalRows: number;
  created: number;
  failed: number;
  totalMatches: number;
  results: {
    row: number;
    ok: boolean;
    email: string;
    error?: string;
    matchesCreated?: number;
  }[];
};

export function AdminCandidateCsvImport() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "loading">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<ImportResult | null>(null);

  async function handleImport(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose an Excel file to import.");
      return;
    }

    setStatus("loading");
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.set("file", file);

    try {
      const response = await fetch("/api/admin/candidates/import", {
        method: "POST",
        body: formData,
      });

      const data = (await response.json()) as ImportResult & { error?: string };

      if (!response.ok) {
        setError(data.error ?? "Import failed.");
        return;
      }

      setResult(data);
      if (data.created > 0) {
        router.refresh();
      }
    } catch {
      setError("Import failed. Try again.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <div className="space-y-8">
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
        <h2 className="text-lg font-semibold">Download Excel template</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          <strong className="text-foreground">Excel is recommended</strong> for
          People Prime — it avoids CSV comma mistakes. The workbook has three
          sheets: <em>Instructions</em>, <em>Valid values</em> (copy options
          from here), and <em>Candidates</em> (fill your rows).
        </p>
        <a
          href={CANDIDATE_IMPORT_TEMPLATE_PATH}
          download
          className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-transform hover:-translate-y-0.5"
        >
          <Download className="h-4 w-4" />
          Download Excel template (.xlsx)
        </a>
      </div>

      <form
        onSubmit={handleImport}
        className="rounded-2xl border border-border bg-card p-6 sm:p-8"
      >
        <h2 className="text-lg font-semibold">Upload filled template</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Fill the <strong>Candidates</strong> sheet, delete the sample rows, save
          as .xlsx, and upload here. CSV also works if you export from Excel.
        </p>

        <div className="mt-6">
          <input
            type="file"
            accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setResult(null);
              setError("");
            }}
            className="block w-full text-sm text-muted-foreground file:mr-4 file:rounded-full file:border-0 file:bg-primary file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary-foreground"
          />
        </div>

        {error && (
          <div className="mt-4">
            <ErrorBanner message={error} />
          </div>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          <PrimaryButton type="submit" disabled={!file || status === "loading"}>
            <Upload className="h-4 w-4" />
            {status === "loading" ? "Importing..." : "Import candidates"}
          </PrimaryButton>
          <Link
            href="/admin/candidates"
            className="inline-flex items-center justify-center gap-2 rounded-full border border-border px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to registry
          </Link>
        </div>
      </form>

      {result && (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
          <h2 className="text-lg font-semibold">Import summary</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {result.created} created · {result.failed} failed ·{" "}
            {result.totalMatches} match{result.totalMatches === 1 ? "" : "es"}{" "}
            created
          </p>

          <ul className="mt-4 divide-y divide-border text-sm">
            {result.results.map((row) => (
              <li key={`${row.row}-${row.email}`} className="py-3">
                <span className="font-medium">Row {row.row}</span> · {row.email}
                {row.ok ? (
                  <span className="text-muted-foreground">
                    {" "}
                    — added
                    {row.matchesCreated
                      ? ` (${row.matchesCreated} match${row.matchesCreated === 1 ? "" : "es"})`
                      : ""}
                  </span>
                ) : (
                  <span className="text-destructive"> — {row.error}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
