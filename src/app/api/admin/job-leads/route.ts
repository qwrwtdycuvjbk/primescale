import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { searchRemoteTechJobs } from "@/lib/openweb-ninja";
import { jobLeadsApi } from "@/lib/api";

async function assertAdmin() {
  const { user, profile } = await getSessionProfile();
  if (!user || profile?.role !== "admin") return null;
  return user;
}

export async function GET(request: Request) {
  const user = await assertAdmin();
  if (!user) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query") ?? undefined;
  const datePosted = (searchParams.get("datePosted") ?? "3days") as
    | "today"
    | "3days"
    | "week"
    | "month"
    | "all";
  const country = searchParams.get("country") ?? "worldwide";
  const pages = Number(searchParams.get("pages") ?? "1");

  // Attempt Django REST API first for saved/stored job leads if any
  try {
    const djangoLeads = await jobLeadsApi.listLeads({ query, country });
    if (djangoLeads && djangoLeads.ok && djangoLeads.count > 0) {
      return NextResponse.json({
        ok: true,
        count: djangoLeads.count,
        queriesUsed: query ? [query] : [],
        countriesUsed: country ? [country] : [],
        leads: djangoLeads.leads,
      });
    }
  } catch {
    // Fall back to live search
  }

  const result = await searchRemoteTechJobs({
    query,
    datePosted,
    country,
    pages: Number.isFinite(pages) ? pages : 1,
  });

  if (!result.ok) {
    return NextResponse.json({ error: result.error }, { status: result.status });
  }

  return NextResponse.json({
    ok: true,
    count: result.leads.length,
    queriesUsed: result.queriesUsed,
    countriesUsed: result.countriesUsed,
    leads: result.leads,
  });
}
