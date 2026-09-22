"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Power, CheckCircle2, Trash2, Loader2, AlertTriangle } from "lucide-react";

interface CandidateAccountActionButtonsProps {
  candidateId: string;
  candidateName: string;
  candidateEmail?: string;
  isActive: boolean;
  compact?: boolean;
  onStatusChange?: (newStatus: boolean) => void;
  onDeleted?: () => void;
}

export function CandidateAccountActionButtons({
  candidateId,
  candidateName,
  candidateEmail,
  isActive: initialIsActive,
  compact = false,
  onStatusChange,
  onDeleted,
}: CandidateAccountActionButtonsProps) {
  const router = useRouter();
  const [isActive, setIsActive] = useState<boolean>(initialIsActive);
  const [activeModal, setActiveModal] = useState<"activate" | "deactivate" | "delete" | null>(null);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function handleConfirmAction() {
    if (!activeModal) return;
    const action = activeModal;
    setError(null);

    try {
      if (action === "activate") {
        const res = await fetch(`/api/admin/candidates/${candidateId}/activate`, {
          method: "POST",
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to activate account");
        setIsActive(true);
        onStatusChange?.(true);
      } else if (action === "deactivate") {
        const res = await fetch(`/api/admin/candidates/${candidateId}/deactivate`, {
          method: "POST",
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to deactivate account");
        setIsActive(false);
        onStatusChange?.(false);
      } else if (action === "delete") {
        const res = await fetch(`/api/admin/candidates/${candidateId}/delete`, {
          method: "DELETE",
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to delete account");
        onDeleted?.();
      }

      setActiveModal(null);
      startTransition(() => {
        router.refresh();
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Action failed");
    }
  }

  return (
    <>
      <div className={`flex items-center ${compact ? "gap-1.5 flex-wrap" : "gap-2"}`}>
        {isActive ? (
          <button
            type="button"
            onClick={() => {
              setError(null);
              setActiveModal("deactivate");
            }}
            className={
              compact
                ? "inline-flex items-center gap-1 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 transition-colors"
                : "inline-flex items-center gap-1.5 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs font-semibold text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 transition-colors"
            }
            title="Deactivate candidate account access"
          >
            <Power className="h-3.5 w-3.5" />
            Deactivate
          </button>
        ) : (
          <button
            type="button"
            onClick={() => {
              setError(null);
              setActiveModal("activate");
            }}
            className={
              compact
                ? "inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 transition-colors"
                : "inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 transition-colors"
            }
            title="Activate candidate account access"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Activate
          </button>
        )}

        <button
          type="button"
          onClick={() => {
            setError(null);
            setActiveModal("delete");
          }}
          className={
            compact
              ? "inline-flex items-center gap-1 rounded-lg border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/20 transition-colors"
              : "inline-flex items-center gap-1.5 rounded-xl border border-destructive/30 bg-destructive/10 px-3.5 py-2 text-xs font-semibold text-destructive hover:bg-destructive/20 transition-colors"
          }
          title="Permanently delete candidate account"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete
        </button>
      </div>

      {/* Confirmation Modal */}
      {activeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 text-left whitespace-normal animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-3xl border border-border bg-card p-6 sm:p-7 shadow-2xl space-y-4 text-left whitespace-normal animate-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5">
              {activeModal === "delete" ? (
                <div className="rounded-2xl bg-destructive/10 p-3 text-destructive shrink-0">
                  <Trash2 className="h-6 w-6" />
                </div>
              ) : activeModal === "deactivate" ? (
                <div className="rounded-2xl bg-amber-500/10 p-3 text-amber-600 dark:text-amber-400 shrink-0">
                  <AlertTriangle className="h-6 w-6" />
                </div>
              ) : (
                <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-600 dark:text-emerald-400 shrink-0">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
              )}
              <div className="min-w-0 flex-1">
                <h3 className="text-lg font-bold text-foreground">
                  {activeModal === "activate"
                    ? "Activate Candidate Account"
                    : activeModal === "deactivate"
                      ? "Deactivate Candidate Account"
                      : "Delete Candidate Account"}
                </h3>
                <p className="mt-0.5 text-xs text-muted-foreground break-all">
                  {candidateName} {candidateEmail ? `(${candidateEmail})` : ""}
                </p>
              </div>
            </div>

            <div className="text-sm text-muted-foreground leading-relaxed whitespace-normal break-words">
              {activeModal === "activate" && (
                <p>
                  Activate this candidate account? The candidate will be granted access to log in
                  and use People Remotely again.
                </p>
              )}
              {activeModal === "deactivate" && (
                <p>
                  Are you sure you want to deactivate this candidate account? The candidate will
                  be immediately blocked from logging in with access denied.
                </p>
              )}
              {activeModal === "delete" && (
                <p className="text-foreground/90 font-medium">
                  Are you sure you want to permanently delete this candidate account? All
                  candidate profile records, applications, and matches will be deleted. This action
                  cannot be undone.
                </p>
              )}
            </div>

            {error && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive font-medium whitespace-normal break-words">
                {error}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-border/50">
              <button
                type="button"
                disabled={isPending}
                onClick={() => {
                  if (!isPending) {
                    setActiveModal(null);
                    setError(null);
                  }
                }}
                className="rounded-full border border-border px-4 py-2 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isPending}
                onClick={() => void handleConfirmAction()}
                className={
                  activeModal === "delete"
                    ? "inline-flex items-center gap-1.5 rounded-full bg-destructive px-5 py-2 text-xs font-semibold text-destructive-foreground shadow hover:opacity-90 transition-opacity disabled:opacity-50"
                    : activeModal === "deactivate"
                      ? "inline-flex items-center gap-1.5 rounded-full bg-amber-600 dark:bg-amber-500 px-5 py-2 text-xs font-semibold text-white shadow hover:opacity-90 transition-opacity disabled:opacity-50"
                      : "inline-flex items-center gap-1.5 rounded-full bg-emerald-600 dark:bg-emerald-500 px-5 py-2 text-xs font-semibold text-white shadow hover:opacity-90 transition-opacity disabled:opacity-50"
                }
              >
                {isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {activeModal === "delete"
                  ? "Permanently Delete"
                  : activeModal === "deactivate"
                    ? "Deactivate Account"
                    : "Activate Account"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}