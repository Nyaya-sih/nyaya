"use client";

import { useSearchStore } from "@/lib/stores/search-store";

export function TextSearchInput() {
  const queryText = useSearchStore((state) => state.queryText);
  const setQueryText = useSearchStore((state) => state.setQueryText);
  const minReached = queryText.trim().length >= 100;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <textarea
        value={queryText}
        onChange={(event) => setQueryText(event.target.value)}
        placeholder="Paste your case text here..."
        className="h-48 w-full resize-none rounded-xl border border-[var(--border)] bg-transparent p-4 text-sm text-[var(--neutral-700)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-300)]"
      />
      <div className="mt-3 flex items-center justify-between text-xs text-[var(--neutral-500)]">
        <span>Character count: {queryText.length}/100 minimum</span>
        <span className={minReached ? "text-[var(--success)]" : "text-[var(--neutral-500)]"}>
          {minReached ? "Ready" : "Needs 100+"}
        </span>
      </div>
    </div>
  );
}
