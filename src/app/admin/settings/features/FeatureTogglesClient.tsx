"use client";

import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  RefreshCw,
  Sliders,
  Sparkles,
} from "lucide-react";
import { adminApi, SystemFeatureToggleItem } from "@/lib/api/admin";

interface FeatureTogglesClientProps {
  initialFeatures: SystemFeatureToggleItem[];
  token: string;
}

export function FeatureTogglesClient({
  initialFeatures,
  token,
}: FeatureTogglesClientProps) {
  const [features, setFeatures] = useState<SystemFeatureToggleItem[]>(initialFeatures);
  const [loading, setLoading] = useState<boolean>(false);
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    feature: SystemFeatureToggleItem;
    targetState: boolean;
  } | null>(null);

  async function refreshFeatures() {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await adminApi.getFeatureToggles({ token });
      setFeatures(res.features || []);
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to refresh feature toggles.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleToggle(feature: SystemFeatureToggleItem, newState: boolean) {
    setConfirmDialog(null);
    setUpdatingKey(feature.feature_key);
    setFeedback(null);

    try {
      const updated = await adminApi.updateFeatureToggle(
        feature.feature_key,
        newState,
        { token },
      );

      setFeatures((prev) =>
        prev.map((f) => (f.feature_key === updated.feature_key ? updated : f)),
      );

      setFeedback({
        type: "success",
        message: `Successfully ${newState ? "enabled" : "disabled"} ${feature.name}. Cache invalidated.`,
      });
    } catch (err: unknown) {
      setFeedback({
        type: "error",
        message:
          err instanceof Error
            ? err.message
            : `Failed to update toggle for ${feature.name}.`,
      });
    } finally {
      setUpdatingKey(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Feedback Alert */}
      {feedback && (
        <div
          className={`flex items-center gap-3 rounded-2xl p-4 text-sm ${
            feedback.type === "success"
              ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
              : "border border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          {feedback.type === "success" ? (
            <CheckCircle2 className="h-5 w-5 shrink-0" />
          ) : (
            <AlertCircle className="h-5 w-5 shrink-0" />
          )}
          <span className="font-medium">{feedback.message}</span>
        </div>
      )}

      {/* Global Refresh Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Sliders className="h-4 w-4" />
          <span>Showing {features.length} operational feature switch{features.length === 1 ? "" : "es"}</span>
        </div>
        <button
          onClick={refreshFeatures}
          disabled={loading || updatingKey !== null}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-semibold text-foreground hover:bg-muted transition disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* Feature Cards Grid */}
      <div className="grid grid-cols-1 gap-6">
        {features.map((feature) => {
          const isUpdating = updatingKey === feature.feature_key;
          const isBlockedByEnv = !feature.environment_master_switch;

          return (
            <div
              key={feature.feature_key}
              className="rounded-3xl border border-border bg-card p-6 sm:p-8 shadow-xs transition"
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6">
                <div className="space-y-3 flex-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-0.5 text-xs font-semibold text-primary">
                      <Sparkles className="h-3 w-3" />
                      <span>{feature.name}</span>
                    </div>

                    {/* Effective State Badge */}
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-0.5 text-xs font-semibold ${
                        feature.effective_status
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                          : "bg-muted text-muted-foreground border border-border"
                      }`}
                    >
                      <span
                        className={`h-2 w-2 rounded-full ${
                          feature.effective_status ? "bg-emerald-500" : "bg-muted-foreground/60"
                        }`}
                      />
                      <span>
                        Effective Status: {feature.effective_status ? "ACTIVE" : "INACTIVE"}
                      </span>
                    </span>
                  </div>

                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {feature.description}
                  </p>

                  {/* Metadata & Audit Trail */}
                  <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1 border-t border-border/60">
                    <div>
                      <span className="font-medium text-foreground">Database Toggle:</span>{" "}
                      <span
                        className={
                          feature.is_enabled ? "text-emerald-600 font-semibold" : "text-muted-foreground font-semibold"
                        }
                      >
                        {feature.is_enabled ? "ON" : "OFF"}
                      </span>
                    </div>
                    <div>
                      <span className="font-medium text-foreground">Environment Master Switch:</span>{" "}
                      <span
                        className={
                          feature.environment_master_switch
                            ? "text-emerald-600 font-semibold"
                            : "text-rose-600 font-semibold"
                        }
                      >
                        {feature.environment_master_switch ? "ALLOWED (True)" : "BLOCKED (False)"}
                      </span>
                    </div>
                    {feature.updated_at && (
                      <div>
                        <span className="font-medium text-foreground">Last Modified:</span>{" "}
                        {new Date(feature.updated_at).toLocaleString()}
                        {feature.updated_by && ` by ${feature.updated_by.email}`}
                      </div>
                    )}
                  </div>
                </div>

                {/* Control Action Switch */}
                <div className="flex sm:flex-col items-center sm:items-end justify-between gap-3 pt-2 sm:pt-0">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-semibold text-foreground">
                      Admin Setting:
                    </span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={feature.is_enabled}
                      disabled={isUpdating}
                      onClick={() =>
                        setConfirmDialog({
                          feature,
                          targetState: !feature.is_enabled,
                        })
                      }
                      className={`relative inline-flex h-7 w-13 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:cursor-not-allowed disabled:opacity-50 ${
                        feature.is_enabled ? "bg-primary" : "bg-muted"
                      }`}
                    >
                      <span className="sr-only">Toggle {feature.name}</span>
                      <span
                        aria-hidden="true"
                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out ${
                          feature.is_enabled ? "translate-x-6" : "translate-x-0"
                        }`}
                      >
                        {isUpdating && (
                          <Loader2 className="h-4 w-4 animate-spin text-primary m-1" />
                        )}
                      </span>
                    </button>
                  </div>

                  <span className="text-[11px] text-muted-foreground">
                    {feature.is_enabled ? "Click to disable" : "Click to enable"}
                  </span>
                </div>
              </div>

              {/* Warning banner if blocked by Environment Master Switch */}
              {isBlockedByEnv && (
                <div className="mt-5 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-semibold">
                      Feature is Globally Blocked by Environment Master Switch
                    </p>
                    <p className="leading-relaxed opacity-90">
                      <code>ENABLE_EXTERNAL_JOB_RECOMMENDATIONS=False</code> is configured on this deployment. Even if this admin toggle is set to ON, candidate endpoints and background processing remain fail-closed and disabled until the server environment variable is updated.
                    </p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Confirmation Modal */}
      {confirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-3xl border border-border bg-card p-6 sm:p-7 shadow-xl space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${
                  confirmDialog.targetState
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                    : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                }`}
              >
                <Info className="h-5 w-5" />
              </div>
              <h3 className="text-base font-bold text-foreground">
                Confirm Feature Status Change
              </h3>
            </div>

            <p className="text-sm text-muted-foreground leading-relaxed">
              Are you sure you want to{" "}
              <strong className="text-foreground">
                {confirmDialog.targetState ? "ENABLE" : "DISABLE"}
              </strong>{" "}
              <strong>{confirmDialog.feature.name}</strong>?
            </p>

            <p className="text-xs text-muted-foreground/90 bg-muted/50 p-3 rounded-2xl">
              {confirmDialog.targetState
                ? "Qualified candidates will see recommended external jobs on their dashboards, and background Celery re-evaluations will resume."
                : "Candidate recommendation feeds will immediately be suppressed, feedback submissions will be rejected, and Celery re-evaluations will skip processing."}
            </p>

            <div className="pt-2 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDialog(null)}
                className="rounded-full border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground hover:bg-muted transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() =>
                  handleToggle(
                    confirmDialog.feature,
                    confirmDialog.targetState,
                  )
                }
                className={`inline-flex items-center gap-1.5 rounded-full px-5 py-2 text-xs font-semibold text-primary-foreground hover:opacity-95 transition ${
                  confirmDialog.targetState ? "bg-primary" : "bg-destructive text-destructive-foreground"
                }`}
              >
                <span>Confirm {confirmDialog.targetState ? "Enable" : "Disable"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
