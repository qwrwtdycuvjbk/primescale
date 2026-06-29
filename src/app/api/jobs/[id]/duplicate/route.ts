import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { data: source } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", id)
    .eq("posted_by", user.id)
    .single();

  if (!source) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }

  const { data: copy, error } = await supabase
    .from("jobs")
    .insert({
      company_id: source.company_id,
      posted_by: user.id,
      title: `${source.title} (copy)`,
      description: source.description,
      role_type: source.role_type,
      experience_level: source.experience_level,
      tech_stack: source.tech_stack,
      salary_range: source.salary_range,
      work_type: source.work_type,
      visa_requirements: source.visa_requirements,
      status: "draft",
      jd_quality_score: source.jd_quality_score,
      jd_quality_feedback: source.jd_quality_feedback,
    })
    .select("id")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, jobId: copy.id });
}
