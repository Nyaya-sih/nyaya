"use client";

import { useEffect } from "react";
import { Container } from "@/components/layout/container";

export default function SearchError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error("Search page error:", error);
  }, [error]);

  return (
    <Container className="py-20">
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
        <h2 className="text-xl font-semibold text-[var(--primary-900)]">Search Unavailable</h2>
        <p className="mt-2 text-sm text-[var(--neutral-600)]">
          Failed to load search filters or initialize the search page. The backend API may be
          unreachable.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-4 rounded-full bg-[var(--primary-700)] px-4 py-2 text-xs font-semibold text-white"
        >
          Retry
        </button>
      </div>
    </Container>
  );
}
