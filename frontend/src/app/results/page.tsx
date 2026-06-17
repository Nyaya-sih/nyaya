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
import { motion, useReducedMotion } from "framer-motion";
import { staggerContainer, staggerItem } from "@/lib/utils/motion";

const SEARCH_STEPS = [
  "Generating embeddings",
  "Searching vector database",
  "Reranking candidates",
  "Analyzing similarity",
  "Preparing results",
];

export default function ResultsPage() {
  const reduceMotion = useReducedMotion();
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
  const effectiveWarnings = effectiveResponse?.warnings ?? [];
  const effectiveMode = effectiveResponse?.retrieval_mode ?? "full";
  const queryForExplain = effectiveResponse?.query_summary ?? queryText;
  const loading = shouldFetch && (isLoading || (isFetching && !response));

  return (
    <Container className="space-y-6 pb-20 pt-10">
      {loading && (
        <div className="legal-panel p-6">
          <p className="text-sm text-[var(--neutral-600)]">Searching case index...</p>
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
              className="h-full rounded-full bg-[var(--accent-500)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {effectiveResponse && !loading && (
        <>
          <ResultsHeader response={effectiveResponse} />
          {effectiveMode !== "full" && (
            <div className="legal-panel p-4 text-sm text-[var(--neutral-700)]">
              Search executed in <strong>{effectiveMode}</strong> mode.
              Results may be less precise than full mode.
            </div>
          )}
          {effectiveWarnings.length > 0 && (
            <div className="legal-panel p-4 text-sm text-[var(--neutral-700)]">
              <p className="font-semibold text-[var(--primary-900)]">Search warnings</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {effectiveWarnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          <LegalDisclaimer text={effectiveResponse.disclaimer} />
          <motion.div
            className="grid gap-4"
            variants={staggerContainer}
            initial={reduceMotion ? false : "initial"}
            animate={reduceMotion ? undefined : "animate"}
          >
            {effectiveResponse.results.length ? (
              effectiveResponse.results.map((result) => (
                <motion.div key={result.case_id} variants={staggerItem}>
                  <ResultCard result={result} queryText={queryForExplain} />
                </motion.div>
              ))
            ) : (
              <NoResults />
            )}
          </motion.div>
        </>
      )}

      {!effectiveResponse && !loading && (
        <div className="legal-panel p-10 text-center">
          <h3 className="text-lg font-semibold text-[var(--primary-900)]">No results to display</h3>
          <p className="mt-2 text-sm text-[var(--neutral-600)]">
            Please run a new search or upload a document.
          </p>
          <Link
            href="/search"
            className="legal-button-primary mt-4 inline-flex px-4 py-2 text-xs font-semibold"
          >
            Go to Search
          </Link>
        </div>
      )}

      {!loading && selectedCaseIds.length >= 2 && (
        <motion.div
          className="fixed bottom-8 right-8"
          initial={reduceMotion ? false : { opacity: 0, y: 14 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: [0, -3, 0] }}
          transition={
            reduceMotion
              ? undefined
              : {
                  opacity: { duration: 0.2 },
                  y: { duration: 2.6, repeat: Infinity, ease: "easeInOut" },
                }
          }
        >
          <Link
            href="/compare"
            className="legal-button-primary px-5 py-3 text-xs font-semibold"
          >
            Compare ({selectedCaseIds.length})
          </Link>
        </motion.div>
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
