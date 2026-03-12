"use client";

import { useSearchFilters } from "@/lib/hooks/use-search";
import { useSearchStore } from "@/lib/stores/search-store";
import { SimilarityModeSelect } from "@/components/search/similarity-mode-select";

export function SearchFilters() {
  const { data } = useSearchFilters();
  const filters = useSearchStore((state) => state.filters);
  const updateFilters = useSearchStore((state) => state.updateFilters);
  const topK = useSearchStore((state) => state.topK);
  const setTopK = useSearchStore((state) => state.setTopK);

  return (
    <div className="space-y-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <div>
        <p className="text-xs font-semibold text-[var(--neutral-500)]">Similarity Mode</p>
        <div className="mt-2">
          <SimilarityModeSelect />
        </div>
      </div>

      <div>
        <label htmlFor="max-results-slider" className="text-xs font-semibold text-[var(--neutral-500)]">Max Results</label>
        <input
          id="max-results-slider"
          type="range"
          min={5}
          max={20}
          value={topK}
          onChange={(event) => setTopK(Number(event.target.value))}
          className="mt-2 w-full"
          aria-label={`Maximum results: ${topK}`}
          aria-valuemin={5}
          aria-valuemax={20}
          aria-valuenow={topK}
        />
        <div className="text-xs text-[var(--neutral-600)]">{topK} results</div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <p className="text-xs font-semibold text-[var(--neutral-500)]">Courts</p>
          <div className="mt-2 max-h-32 space-y-2 overflow-auto rounded-lg border border-[var(--border)] p-3" role="group" aria-label="Court filters">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={filters.courts.length === 0}
                onChange={() => updateFilters({ courts: [] })}
                aria-label="All courts"
              />
              All
            </label>
            {data?.courts?.slice(0, 10).map((court) => (
              <label key={court} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={filters.courts.includes(court)}
                  onChange={(event) => {
                    const next = event.target.checked
                      ? [...filters.courts, court]
                      : filters.courts.filter((value) => value !== court);
                    updateFilters({ courts: next });
                  }}
                  aria-label={`Filter by court: ${court}`}
                />
                {court}
              </label>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold text-[var(--neutral-500)]">Case Types</p>
          <div className="mt-2 max-h-32 space-y-2 overflow-auto rounded-lg border border-[var(--border)] p-3" role="group" aria-label="Case type filters">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={filters.caseTypes.length === 0}
                onChange={() => updateFilters({ caseTypes: [] })}
                aria-label="All case types"
              />
              All
            </label>
            {data?.case_types?.map((caseType) => (
              <label key={caseType} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={filters.caseTypes.includes(caseType)}
                  onChange={(event) => {
                    const next = event.target.checked
                      ? [...filters.caseTypes, caseType]
                      : filters.caseTypes.filter((value) => value !== caseType);
                    updateFilters({ caseTypes: next });
                  }}
                  aria-label={`Filter by case type: ${caseType}`}
                />
                {caseType}
              </label>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold text-[var(--neutral-500)]">Verdicts</p>
          <div className="mt-2 max-h-32 space-y-2 overflow-auto rounded-lg border border-[var(--border)] p-3">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={filters.verdicts.length === 0}
                onChange={() => updateFilters({ verdicts: [] })}
                aria-label="All verdicts"
              />
              All
            </label>
            {data?.verdicts?.map((verdict) => (
              <label key={verdict} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={filters.verdicts.includes(verdict)}
                  onChange={(event) => {
                    const next = event.target.checked
                      ? [...filters.verdicts, verdict]
                      : filters.verdicts.filter((value) => value !== verdict);
                    updateFilters({ verdicts: next });
                  }}
                  aria-label={`Filter by verdict: ${verdict}`}
                />
                {verdict}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold text-[var(--neutral-500)]">Year Range</p>
        <div className="mt-2 flex items-center gap-3 text-xs">
          <input
            type="number"
            value={filters.yearMin ?? data?.year_range?.min ?? ""}
            onChange={(event) =>
              updateFilters({ yearMin: event.target.value ? Number(event.target.value) : null })
            }
            className="w-24 rounded-lg border border-[var(--border)] px-2 py-1"
            aria-label="Year range start"
          />
          <span>to</span>
          <input
            type="number"
            value={filters.yearMax ?? data?.year_range?.max ?? ""}
            onChange={(event) =>
              updateFilters({ yearMax: event.target.value ? Number(event.target.value) : null })
            }
            className="w-24 rounded-lg border border-[var(--border)] px-2 py-1"
            aria-label="Year range end"
          />
        </div>
      </div>
    </div>
  );
}
