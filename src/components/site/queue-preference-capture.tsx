"use client";

import { useEffect } from "react";
import { MATCHING_QUEUE_COOKIE } from "@/lib/matching-seats";

/** Persists matching-queue category through signup → onboarding. */
export function QueuePreferenceCapture({
  queue,
}: {
  queue: string | null;
}) {
  useEffect(() => {
    if (!queue) return;
    const maxAge = 60 * 60 * 24 * 7;
    document.cookie = `${MATCHING_QUEUE_COOKIE}=${encodeURIComponent(queue)}; path=/; max-age=${maxAge}; SameSite=Lax`;
  }, [queue]);

  return null;
}
