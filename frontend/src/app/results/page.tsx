"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Container } from "@/components/layout/container";
import { ResultsHeader } from "@/components/results/results-header";
import { ResultCard } from "@/components/results/result-card";
import { ResultSkeleton } from "@/components/results/result-skeleton";
import { NoResults } from "@/components/results/no-results";
import { LegalDisclaimer } from "@/components/results/legal-disclaimer";
import { searchByText } from "@/lib/api/search";
import { getSimilarCases } from "@/lib/api/cases";
import { useCompareStore } from "@/lib/stores/compare-store";
import { useSearchStore } from "@/lib/stores/search-store";
import type { SearchResponse } from "@/lib/api/types";
import { useQuery } from "@tanstack/react-query";

const SEARCH_STEPS = [
  "Generating embeddings",
  "Searching vector database",
  "Reranking candidates",
  "Analyzing similarity",
  "Preparing results",
];

export default function ResultsPage() {
  const params = useSearchParams();
  const queryText = params.get("q") ?? "";
  const caseId = params.get("caseId") ?? "";
  const searchId = params.get("sid") ?? "";
  const [stepIndex, setStepIndex] = useState(0);
  const selectedCaseIds = useCompareStore((state) => state.selectedCaseIds);
  const responseFromStore = useSearchStore((state) =>
    searchId ? state.responsesById[searchId] : null
  );
  const setResponseForId = useSearchStore((state) => state.setResponseForId);

  const shouldFetch = Boolean(caseId || queryText) && !searchId;

  const { data: response, isFetching, isLoading } = useQuery({
    queryKey: ["search", caseId || queryText],
    queryFn: () =>
      caseId
        ? getSimilarCases(caseId)
        : searchByText({ text: queryText, similarity_mode: "combined" }),
    enabled: shouldFetch,
  });

  useEffect(() => {
    if (!searchId) return;
    const cached = sessionStorage.getItem(`search:${searchId}`);
    if (!cached) return;
    const parsed = JSON.parse(cached) as SearchResponse;
    setResponseForId(searchId, parsed);
  }, [searchId, setResponseForId]);

  useEffect(() => {
    if (!isFetching || response) return;
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % SEARCH_STEPS.length);
    }, 900);
    return () => clearInterval(interval);
  }, [isFetching, response]);

  const progress = useMemo(() => ((stepIndex + 1) / SEARCH_STEPS.length) * 100, [stepIndex]);

  const effectiveResponse = response ?? responseFromStore;
  const queryForExplain = effectiveResponse?.query_summary ?? queryText;
  const loading = shouldFetch && (isLoading || (isFetching && !response));

  return (
    <Container className="space-y-6 pb-20 pt-10">
      {loading && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
          <p className="text-sm text-[var(--neutral-600)]">Searching 9,718 cases...</p>
          <div className="mt-4 space-y-2 text-xs text-[var(--neutral-500)]">
            {SEARCH_STEPS.map((step, index) => (
              <div key={step} className="flex items-center gap-2">
                <span>{index <= stepIndex ? "✓" : "○"}</span>
                <span>{step}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 h-2 rounded-full bg-[var(--surface-alt)]">
            <div
              className="h-full rounded-full bg-[var(--accent-400)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {effectiveResponse && !loading && (
        <>
          <ResultsHeader response={effectiveResponse} />
          <LegalDisclaimer text={effectiveResponse.disclaimer} />
          <div className="grid gap-4">
            {effectiveResponse.results.length ? (
              effectiveResponse.results.map((result) => (
                <ResultCard key={result.case_id} result={result} queryText={queryForExplain} />
              ))
            ) : (
              <NoResults />
            )}
          </div>
        </>
      )}

      {!effectiveResponse && !loading && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-10 text-center">
          <h3 className="text-lg font-semibold text-[var(--primary-900)]">No results to display</h3>
          <p className="mt-2 text-sm text-[var(--neutral-600)]">
            Please run a new search or upload a document.
          </p>
          <Link
            href="/search"
            className="mt-4 inline-flex rounded-full bg-[var(--primary-700)] px-4 py-2 text-xs font-semibold text-white"
          >
            Go to Search
          </Link>
        </div>
      )}

      {!loading && selectedCaseIds.length >= 2 && (
        <div className="fixed bottom-8 right-8">
          <Link
            href="/compare"
            className="rounded-full bg-[var(--primary-700)] px-5 py-3 text-xs font-semibold text-white shadow-lg"
          >
            Compare ({selectedCaseIds.length})
          </Link>
        </div>
      )}

      {loading && (
        <div className="grid gap-4">
          {Array.from({ length: 3 }).map((_, index) => (
            <ResultSkeleton key={index} />
          ))}
        </div>
      )}
    </Container>
  );
}
