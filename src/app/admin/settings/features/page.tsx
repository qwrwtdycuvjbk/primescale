import { AdminShell } from "@/components/admin/AdminShell";
import { appContainerClass } from "@/components/site/layout";
import { adminApi, SystemFeatureToggleItem } from "@/lib/api/admin";
import { requireAdmin, getAccessToken } from "@/lib/auth";
import { FeatureTogglesClient } from "./FeatureTogglesClient";

export const metadata = {
  title: "Feature Management | Admin Settings",
};

export default async function AdminFeaturesSettingsPage() {
  const { profile } = await requireAdmin();
  const token = await getAccessToken();

  let initialFeatures: SystemFeatureToggleItem[] = [];
  let errorMsg: string | null = null;

  try {
    const res = await adminApi.getFeatureToggles({ token });
    initialFeatures = res.features || [];
  } catch (err: unknown) {
    errorMsg = err instanceof Error ? err.message : "Failed to load feature toggles.";
  }

  return (
    <AdminShell name={profile?.full_name || "Admin"} activePath="/admin/settings/features">
      <main className={`${appContainerClass} py-8 sm:py-10`}>
        {/* Breadcrumb & Header */}
        <div className="mb-8 border-b border-border pb-6">
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
            <span>Admin</span>
            <span>/</span>
            <span>Settings</span>
            <span>/</span>
            <span className="text-foreground font-medium">Feature Management</span>
          </div>
          <h1 className="display-headline text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            Feature Management & Platform Switches
          </h1>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            Centralized operational toggles. Changes take effect across candidate interfaces and background AI processing pipelines in real time.
          </p>
        </div>

        {errorMsg ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-6 text-center text-sm text-destructive">
            <p className="font-semibold">Unable to load feature configurations</p>
            <p className="mt-1 text-xs opacity-90">{errorMsg}</p>
          </div>
        ) : (
          <FeatureTogglesClient initialFeatures={initialFeatures} token={token || ""} />
        )}
      </main>
    </AdminShell>
  );
}
