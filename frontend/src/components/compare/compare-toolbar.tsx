"use client";

import { COMPARE_FIELDS, useCompareStore } from "@/lib/stores/compare-store";

export function CompareToolbar() {
  const visibleFields = useCompareStore((state) => state.visibleFields);
  const toggleField = useCompareStore((state) => state.toggleField);

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 text-xs">
      <p className="text-[var(--neutral-500)]">Show:</p>
      <div className="mt-2 flex flex-wrap gap-3">
        {COMPARE_FIELDS.map((field) => (
          <label key={field} className="flex items-center gap-2" aria-label={`Toggle ${field} visibility`}>
            <input
              type="checkbox"
              checked={visibleFields.includes(field)}
              onChange={() => toggleField(field)}
              aria-label={`Show ${field} in comparison`}
            />
            {field}
          </label>
        ))}
      </div>
    </div>
  );
}
