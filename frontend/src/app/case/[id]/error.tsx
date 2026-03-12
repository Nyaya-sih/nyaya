"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Container } from "@/components/layout/container";

export default function CaseError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error("Case detail error:", error);
  }, [error]);

  return (
    <Container className="py-20">
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
        <h2 className="text-xl font-semibold text-[var(--primary-900)]">Case Not Found</h2>
        <p className="mt-2 text-sm text-[var(--neutral-600)]">
          Could not load the requested case. It may not exist or the server may be unavailable.
        </p>
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="rounded-full bg-[var(--primary-700)] px-4 py-2 text-xs font-semibold text-white"
          >
            Retry
          </button>
          <Link
            href="/search"
            className="rounded-full border border-[var(--border)] px-4 py-2 text-xs text-[var(--neutral-600)]"
          >
            Back to Search
          </Link>
        </div>
      </div>
    </Container>
  );
}
