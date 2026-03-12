"use client";

import { useSearchStore } from "@/lib/stores/search-store";

export function SimilarityModeSelect() {
  const similarityMode = useSearchStore((state) => state.similarityMode);
  const setSimilarityMode = useSearchStore((state) => state.setSimilarityMode);

  return (
    <div className="flex flex-wrap gap-3 text-xs">
      {[
        { label: "Combined", value: "combined" },
        { label: "Factual", value: "factual" },
        { label: "Legal", value: "legal" },
      ].map((item) => (
        <button
          key={item.value}
          type="button"
          onClick={() => setSimilarityMode(item.value as "combined" | "factual" | "legal")}
          className={`rounded-full border px-4 py-1 ${
            similarityMode === item.value
              ? "border-[var(--primary-700)] bg-[var(--primary-700)] text-white"
              : "border-[var(--border)] text-[var(--neutral-600)]"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
