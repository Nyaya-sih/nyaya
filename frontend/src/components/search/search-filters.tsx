"use client";

import { useSearchFilters } from "@/lib/hooks/use-search";
import { useSearchStore } from "@/lib/stores/search-store";
import { SimilarityModeSelect } from "@/components/search/similarity-mode-select";
import { Button } from "@/components/ui/button";
import { SlidersHorizontal } from "lucide-react";

function FilterGroup({
  title,
  items,
  selected,
  onToggle,
  allLabel,
}: {
  title: string;
  items: string[];
  selected: string[];
  onToggle: (value: string) => void;
  allLabel: string;
}) {
  return (
    <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">
          {title}
        </p>
        <span className="text-[11px] text-[var(--neutral-500)]">{selected.length || "All"}</span>
      </div>
      <div className="max-h-44 space-y-2 overflow-auto pr-1">
        <button
          type="button"
          onClick={() => {
            if (selected.length > 0) {
              onToggle("__clear__");
            }
          }}
          className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
            selected.length === 0
              ? "border-[var(--primary-400)] bg-[var(--primary-50)] text-[var(--primary-800)]"
              : "border-[var(--border)] bg-[var(--surface-alt)] text-[var(--neutral-600)] hover:border-[var(--primary-300)]"
          }`}
        >
          {allLabel}
        </button>

        {items.map((value) => {
          const isActive = selected.includes(value);
          return (
            <button
              key={value}
              type="button"
              onClick={() => onToggle(value)}
              aria-pressed={isActive}
              className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition ${
                isActive
                  ? "border-[var(--accent-400)] bg-[var(--accent-100)] text-[var(--neutral-800)]"
                  : "border-[var(--border)] bg-[var(--surface)] text-[var(--neutral-700)] hover:border-[var(--primary-300)] hover:bg-[var(--surface-alt)]"
              }`}
            >
              {value}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SearchFilters() {
  const { data } = useSearchFilters();
  const filters = useSearchStore((state) => state.filters);
  const updateFilters = useSearchStore((state) => state.updateFilters);
  const clearFilters = useSearchStore((state) => state.clearFilters);
  const topK = useSearchStore((state) => state.topK);
  const setTopK = useSearchStore((state) => state.setTopK);

  const activeFilterCount =
    filters.courts.length +
    filters.caseTypes.length +
    filters.verdicts.length +
    (filters.yearMin ? 1 : 0) +
    (filters.yearMax ? 1 : 0);

  return (
    <div className="space-y-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--primary-900)]">
          <SlidersHorizontal className="h-4 w-4" />
          Search Filters
          {activeFilterCount > 0 && (
            <span className="rounded-full bg-[var(--accent-100)] px-2 py-0.5 text-[11px] text-[var(--neutral-800)]">
              {activeFilterCount} active
            </span>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={clearFilters}>
          Reset Filters
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_0.9fr]">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-alt)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">
            Similarity Mode
          </p>
          <div className="mt-2">
            <SimilarityModeSelect />
          </div>
        </div>

        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-alt)] p-4">
          <div className="flex items-center justify-between">
            <label htmlFor="max-results-slider" className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">
              Max Results
            </label>
            <span className="text-xs font-semibold text-[var(--primary-800)]">{topK}</span>
          </div>
          <input
            id="max-results-slider"
            type="range"
            min={5}
            max={20}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
            className="mt-3 w-full accent-[var(--primary-600)]"
            aria-label={`Maximum results: ${topK}`}
            aria-valuemin={5}
            aria-valuemax={20}
            aria-valuenow={topK}
          />
          <div className="mt-2 h-1.5 rounded-full bg-[var(--surface)]">
            <div
              className="h-1.5 rounded-full bg-[var(--primary-600)]"
              style={{ width: `${((topK - 5) / 15) * 100}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-[var(--neutral-600)]">Higher values broaden the candidate set.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <FilterGroup
          title="Courts"
          items={data?.courts?.slice(0, 12) ?? []}
          selected={filters.courts}
          allLabel="All Courts"
          onToggle={(court) => {
            if (court === "__clear__") {
              updateFilters({ courts: [] });
              return;
            }
            const next = filters.courts.includes(court)
              ? filters.courts.filter((value) => value !== court)
              : [...filters.courts, court];
            updateFilters({ courts: next });
          }}
        />

        <FilterGroup
          title="Case Types"
          items={data?.case_types ?? []}
          selected={filters.caseTypes}
          allLabel="All Case Types"
          onToggle={(caseType) => {
            if (caseType === "__clear__") {
              updateFilters({ caseTypes: [] });
              return;
            }
            const next = filters.caseTypes.includes(caseType)
              ? filters.caseTypes.filter((value) => value !== caseType)
              : [...filters.caseTypes, caseType];
            updateFilters({ caseTypes: next });
          }}
        />

        <FilterGroup
          title="Verdicts"
          items={data?.verdicts ?? []}
          selected={filters.verdicts}
          allLabel="All Verdicts"
          onToggle={(verdict) => {
            if (verdict === "__clear__") {
              updateFilters({ verdicts: [] });
              return;
            }
            const next = filters.verdicts.includes(verdict)
              ? filters.verdicts.filter((value) => value !== verdict)
              : [...filters.verdicts, verdict];
            updateFilters({ verdicts: next });
          }}
        />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-alt)] p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">
          Year Range
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
          <input
            type="number"
            value={filters.yearMin ?? data?.year_range?.min ?? ""}
            onChange={(event) =>
              updateFilters({ yearMin: event.target.value ? Number(event.target.value) : null })
            }
            className="w-28 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            aria-label="Year range start"
            placeholder="From"
          />
          <span className="text-[var(--neutral-500)]">to</span>
          <input
            type="number"
            value={filters.yearMax ?? data?.year_range?.max ?? ""}
            onChange={(event) =>
              updateFilters({ yearMax: event.target.value ? Number(event.target.value) : null })
            }
            className="w-28 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
            aria-label="Year range end"
            placeholder="To"
          />
        </div>
      </div>
    </div>
  );
}
