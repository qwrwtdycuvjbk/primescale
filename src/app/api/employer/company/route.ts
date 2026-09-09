import { NextResponse } from "next/server";
import { getSessionProfile, getAccessToken } from "@/lib/auth";
import type { CompanyInput } from "@/lib/types";
import { companiesApi } from "@/lib/api";

export async function POST(request: Request) {
  const { user } = await getSessionProfile();
  const token = await getAccessToken();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = (await request.json()) as CompanyInput & { workEmail?: string };

  if (!body.name?.trim()) {
    return NextResponse.json({ error: "Company name is required" }, { status: 400 });
  }

  try {
    const res = await companiesApi.saveMyCompany(
      {
        ...body,
        workEmail: body.workEmail ?? user.email ?? "",
      },
      { token },
    );
    if (res && res.companyId) {
      return NextResponse.json({
        ok: true,
        companyId: res.companyId,
        domainVerified: res.domainVerified,
      });
    }
    return NextResponse.json({ error: "Failed to save company" }, { status: 400 });
  } catch (apiErr: any) {
    return NextResponse.json(
      { error: apiErr?.message || apiErr?.error || "Failed to save company" },
      { status: apiErr?.status || 400 },
    );
  }
}
