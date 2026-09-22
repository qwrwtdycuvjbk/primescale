import Link from "next/link";
import {
  Building2,
  Briefcase,
  Users,
  Shield,
} from "lucide-react";
import { AdminShell } from "@/components/admin/AdminShell";
import { appMainClass } from "@/components/site/layout";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { companiesApi } from "@/lib/api/companies";
import { EmployersRegistryTable } from "@/components/admin/EmployersRegistryTable";

export default async function AdminEmployersPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    status?: string;
    industry?: string;
  }>;
}) {
  const { profile } = await requireAdmin();
  const token = await getAccessToken();
  const params = await searchParams;

  let employersData: {
    employers: any[];
    totalCount: number;
    activeCount: number;
    count: number;
  } = {
    employers: [],
    totalCount: 0,
    activeCount: 0,
    count: 0,
  };

  try {
    const res = await companiesApi.listAdminEmployers(
      {
        q: params.q,
        status: params.status,
        industry: params.industry,
      },
      { token }
    );
    if (res && Array.isArray(res.employers)) {
      employersData = res;
    }
  } catch (err) {
    console.error("Failed to load admin employers:", err);
  }

  const employers = employersData.employers || [];
  const totalCount = employersData.totalCount ?? employersData.count ?? employers.length;
  const activeCount = employersData.activeCount ?? employers.filter((e) => e.is_active).length;
  const inactiveCount = Math.max(0, totalCount - activeCount);

  return (
    <AdminShell name={profile.full_name} activePath="/admin/employers">
      <main className={appMainClass}>
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="display-headline text-3xl sm:text-4xl">
                Employer <span className="italic text-foreground">registry.</span>
              </h1>
              <span className="rounded-full bg-primary/10 text-primary border border-primary/20 px-3 py-0.5 text-xs font-bold uppercase tracking-wider">
                Read-Only
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              Monitor registered hiring organizations, hiring managers, company profiles, and posted positions.
            </p>
          </div>
        </div>

        {/* Stats Row */}
        <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Total Employers</span>
              <Building2 className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">{totalCount}</p>
          </div>

          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Active Organizations</span>
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">{activeCount}</p>
          </div>

          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Inactive Organizations</span>
              <span className="h-2 w-2 rounded-full bg-red-500" />
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">{inactiveCount}</p>
          </div>

          <div className="rounded-2xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Platform Scope</span>
              <Shield className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-2 text-xs font-semibold text-muted-foreground">
              Strictly Read-Only Monitor
            </p>
          </div>
        </div>

        {/* Employers Registry Table */}
        <div className="mt-8">
          <EmployersRegistryTable
            initialEmployers={employers}
            totalCount={totalCount}
            activeCount={activeCount}
          />
        </div>
      </main>
    </AdminShell>
  );
}