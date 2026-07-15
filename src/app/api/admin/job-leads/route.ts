import { NextResponse } from "next/server";
import { getSessionProfile } from "@/lib/auth";
import { searchRemoteTechJobs } from "@/lib/openweb-ninja";

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
  const country = searchParams.get("country") ?? "us";
  const pages = Number(searchParams.get("pages") ?? "1");

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
    leads: result.leads,
  });
}
