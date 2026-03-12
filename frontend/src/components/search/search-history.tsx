"use client";

import { useSearchStore } from "@/lib/stores/search-store";

export function SearchHistory() {
  const recentSearches = useSearchStore((state) => state.recentSearches);

  if (!recentSearches.length) return null;

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <p className="text-xs font-semibold text-[var(--neutral-500)]">Recent searches</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {recentSearches.map((search) => (
          <span
            key={`${search.query}-${search.timestamp}`}
            className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--neutral-600)]"
          >
            {search.query.slice(0, 40)}
          </span>
        ))}
      </div>
    </div>
  );
}
