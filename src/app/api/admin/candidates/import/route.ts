import { NextResponse } from "next/server";
import { createAdminCandidate } from "@/lib/admin-create-candidate";
import {
  parseCandidateImportFile,
  validateCandidateImportRow,
  type CsvImportRowResult,
} from "@/lib/admin-candidate-csv";
import { getSessionProfile } from "@/lib/auth";
import { getServiceClient } from "@/lib/supabase/service";

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") return null;
  return user;
}

export async function POST(request: Request) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  if (!getServiceClient()) {
    return NextResponse.json(
      {
        error:
          "SUPABASE_SERVICE_ROLE_KEY is not available on the server. Add it in Vercel (Production), then redeploy.",
      },
      { status: 503 },
    );
  }

  const formData = await request.formData();
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Upload an Excel (.xlsx) or CSV file." }, { status: 400 });
  }

  const parsed = await parseCandidateImportFile(file);

  if (parsed.error) {
    return NextResponse.json({ error: parsed.error }, { status: 400 });
  }

  const results: CsvImportRowResult[] = [];
  let created = 0;
  let totalMatches = 0;

  for (const { rowNumber, input } of parsed.rows) {
    const validationError = validateCandidateImportRow(input, rowNumber);
    if (validationError) {
      results.push({
        row: rowNumber,
        ok: false,
        email: input.email,
        error: validationError,
      });
      continue;
    }

    const result = await createAdminCandidate(input);
    if (!result.ok) {
      results.push({
        row: rowNumber,
        ok: false,
        email: input.email,
        error: result.error,
      });
      continue;
    }

    created += 1;
    totalMatches += result.matchesCreated;
    results.push({
      row: rowNumber,
      ok: true,
      email: input.email,
      matchesCreated: result.matchesCreated,
    });
  }

  return NextResponse.json({
    ok: true,
    totalRows: parsed.rows.length,
    created,
    failed: results.filter((row) => !row.ok).length,
    totalMatches,
    results,
  });
}
