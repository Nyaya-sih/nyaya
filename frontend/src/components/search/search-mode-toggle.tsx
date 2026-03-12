"use client";

import { useSearchStore } from "@/lib/stores/search-store";

export function SearchModeToggle() {
  const searchMode = useSearchStore((state) => state.searchMode);
  const setSearchMode = useSearchStore((state) => state.setSearchMode);

  return (
    <div className="flex rounded-full border border-[var(--border)] bg-[var(--surface)] p-1 text-sm">
      {[
        { label: "Upload Document", value: "upload" },
        { label: "Paste Text", value: "text" },
      ].map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => setSearchMode(item.value as "upload" | "text")}
          className={`flex-1 rounded-full px-4 py-2 text-xs font-semibold transition ${
            searchMode === item.value
              ? "bg-[var(--primary-700)] text-white"
              : "text-[var(--neutral-600)]"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
