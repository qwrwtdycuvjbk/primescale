import { promises as fs } from "fs";
import path from "path";
import { NextResponse } from "next/server";
import { getSupabase } from "@/lib/supabase";
import type { RoleSubmission, RoleSubmissionInput } from "@/lib/types";

const DATA_DIR = path.join(process.cwd(), "data");
const DATA_FILE = path.join(DATA_DIR, "roles.json");

async function readSubmissions(): Promise<RoleSubmission[]> {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf-8");
    return JSON.parse(raw) as RoleSubmission[];
  } catch {
    return [];
  }
}

async function saveToFile(submission: RoleSubmission) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  const existing = await readSubmissions();
  existing.unshift(submission);
  await fs.writeFile(DATA_FILE, JSON.stringify(existing, null, 2));
}

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validateInput(body: Partial<RoleSubmissionInput>): string | null {
  const required: (keyof RoleSubmissionInput)[] = [
    "companyName",
    "contactName",
    "email",
    "phone",
    "jobTitle",
    "roleType",
    "experienceLevel",
    "techStack",
    "description",
  ];

  for (const field of required) {
    if (!body[field]?.toString().trim()) {
      return `Missing required field: ${field}`;
    }
  }

  if (!isValidEmail(body.email!.trim())) {
    return "Invalid email address";
  }

  return null;
}

function buildSubmission(body: RoleSubmissionInput): RoleSubmission {
  return {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    companyName: body.companyName.trim(),
    contactName: body.contactName.trim(),
    email: body.email.trim().toLowerCase(),
    phone: body.phone.trim(),
    jobTitle: body.jobTitle.trim(),
    roleType: body.roleType,
    experienceLevel: body.experienceLevel,
    techStack: body.techStack.trim(),
    salaryRange: body.salaryRange?.trim() || undefined,
    description: body.description.trim(),
    notes: body.notes?.trim() || undefined,
    submissionType: body.submissionType ?? "manual_form",
  };
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as Partial<RoleSubmissionInput>;
    const error = validateInput(body);

    if (error) {
      return NextResponse.json({ error }, { status: 400 });
    }

    const submission = buildSubmission(body as RoleSubmissionInput);
    const supabase = getSupabase();

    if (!supabase) {
      if (process.env.VERCEL) {
        console.error("Supabase env vars missing on Vercel");
        return NextResponse.json(
          { error: "Server configuration error. Please try again later." },
          { status: 503 },
        );
      }

      await saveToFile(submission);
      return NextResponse.json({ success: true, id: submission.id });
    }

    const row: Record<string, string | null> = {
      company_name: submission.companyName,
      contact_name: submission.contactName,
      email: submission.email,
      phone: submission.phone,
      job_title: submission.jobTitle,
      role_type: submission.roleType,
      experience_level: submission.experienceLevel,
      tech_stack: submission.techStack,
      salary_range: submission.salaryRange ?? null,
      description: submission.description,
      notes: submission.notes ?? null,
      submission_type: submission.submissionType,
    };

    const { error: dbError } = await supabase
      .from("role_submissions")
      .insert(row);

    if (dbError) {
      console.error("Supabase insert error:", dbError);
      return NextResponse.json(
        { error: "Failed to save role submission" },
        { status: 500 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Role submission error:", error);
    return NextResponse.json(
      { error: "Failed to save role submission" },
      { status: 500 },
    );
  }
}
