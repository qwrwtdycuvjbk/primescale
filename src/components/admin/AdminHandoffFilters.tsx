"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { HandoffStatus } from "@/lib/types";

const filters: { value: "all" | HandoffStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "contacted", label: "Contacted" },
  { value: "intro_made", label: "Intro made" },
  { value: "closed", label: "Closed" },
];

export function AdminHandoffFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const active = searchParams.get("status") ?? "all";

  return (
    <div className="flex flex-wrap gap-2">
      {filters.map((filter) => (
        <button
          key={filter.value}
          type="button"
          onClick={() => {
            const params = new URLSearchParams(searchParams.toString());
            if (filter.value === "all") params.delete("status");
            else params.set("status", filter.value);
            const query = params.toString();
            router.push(query ? `/admin/handoffs?${query}` : "/admin/handoffs");
          }}
          className={`rounded-full px-4 py-2 text-sm font-medium transition ${
            active === filter.value
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          {filter.label}
        </button>
      ))}
    </div>
  );
}
