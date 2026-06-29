import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  defaultJobExpiry,
  isValidSalaryRange,
  isWorkEmailDomainVerified,
} from "@/lib/employer";
import { parseSkills } from "@/lib/matching";
import { runMatchingForJob } from "@/lib/match-runner";
import type { CompanyInput } from "@/lib/types";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as CompanyInput & { workEmail?: string };

  if (!body.name?.trim()) {
    return NextResponse.json({ error: "Company name is required" }, { status: 400 });
  }

  const profileComplete = Boolean(
    body.name?.trim() &&
      body.size &&
      body.description?.trim() &&
      body.hqCity?.trim() &&
      body.industry?.trim(),
  );

  const domainVerified = isWorkEmailDomainVerified(
    body.workEmail ?? user.email ?? "",
    body.website,
  );

  const row = {
    owner_id: user.id,
    name: body.name.trim(),
    website: body.website?.trim() || null,
    size: body.size || null,
    description: body.description?.trim() || null,
    hq_city: body.hqCity?.trim() || null,
    industry: body.industry || null,
    remote_culture_statement: body.remoteCultureStatement?.trim() || null,
    logo_url: body.logoUrl || null,
    domain_verified: domainVerified,
    profile_complete: profileComplete,
    country: "US",
    updated_at: new Date().toISOString(),
  };

  const { data: existing } = await supabase
    .from("companies")
    .select("id")
    .eq("owner_id", user.id)
    .maybeSingle();

  if (existing) {
    const { error } = await supabase
      .from("companies")
      .update(row)
      .eq("owner_id", user.id);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, companyId: existing.id, domainVerified });
  }

  const { data, error } = await supabase
    .from("companies")
    .insert(row)
    .select("id")
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  await supabase.from("company_members").insert({
    company_id: data.id,
    user_id: user.id,
    member_role: "admin",
  });

  return NextResponse.json({ ok: true, companyId: data.id, domainVerified });
}
