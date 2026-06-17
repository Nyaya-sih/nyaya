"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Scale, Sparkles } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import type { SearchResult } from "@/lib/api/types";
import { SimilarityScoreRing } from "@/components/results/similarity-score-ring";
import { DimensionScores } from "@/components/results/dimension-scores";
import { VerdictBadge } from "@/components/shared/verdict-badge";
import { CourtBadge } from "@/components/shared/court-badge";
import { truncate } from "@/lib/utils/truncate";
import { useCompareStore } from "@/lib/stores/compare-store";
import { getAiExplanation } from "@/lib/api/search";

export function ResultCard({ result, queryText }: { result: SearchResult; queryText: string }) {
  const reduceMotion = useReducedMotion();
  const isSelected = useCompareStore((state) => state.isSelected(String(result.case_id)));
  const addCase = useCompareStore((state) => state.addCase);
  const removeCase = useCompareStore((state) => state.removeCase);
  const limitReached = useCompareStore((state) => state.limitReached);
  const dismissLimitReached = useCompareStore((state) => state.dismissLimitReached);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  const handleToggleCompare = () => {
    if (isSelected) {
      removeCase(String(result.case_id));
    } else {
      addCase(String(result.case_id));
    }
  };

  useEffect(() => {
    if (limitReached) {
      const timer = setTimeout(dismissLimitReached, 3000);
      return () => clearTimeout(timer);
    }
  }, [limitReached, dismissLimitReached]);

  const handleExplain = async () => {
    if (loading) return;
    setLoading(true);
    try {
      const response = await getAiExplanation(queryText, result.case_id);
      setExplanation(response.explanation);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.article
      className="legal-panel p-6"
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      whileHover={reduceMotion ? undefined : { y: -2 }}
    >
      <div className="flex flex-col gap-6 md:flex-row md:items-center">
        <SimilarityScoreRing value={result.combined_score} />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-[var(--primary-900)]">
              {result.case_title}
            </h3>
            <CourtBadge court={result.court} />
            <VerdictBadge verdict={result.verdict} />
          </div>
          <p className="mt-2 text-sm text-[var(--neutral-600)]">
            {truncate(result.similarity_explanation, 160)}
          </p>
          <div className="mt-4">
            <DimensionScores scores={result.dimensions} semanticScore={result.combined_score} />
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link
          href={`/case/${encodeURIComponent(String(result.case_id))}`}
          className="legal-button-secondary inline-flex items-center gap-2 px-4 py-2 text-xs"
        >
          <Scale className="h-4 w-4" />
          View Details
        </Link>
        <button
          type="button"
          onClick={handleToggleCompare}
          aria-label={isSelected ? `Remove ${result.case_title} from comparison` : `Add ${result.case_title} to comparison`}
          aria-pressed={isSelected}
          className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold ${
            isSelected
              ? "legal-button-primary"
              : "legal-button-secondary"
          }`}
        >
          {isSelected ? "Selected" : "Compare"}
        </button>
        <button
          type="button"
          onClick={handleExplain}
          disabled={loading}
          aria-label={`Get AI explanation for ${result.case_title}`}
          className="legal-button-secondary inline-flex items-center gap-2 px-4 py-2 text-xs"
        >
          <Sparkles className="h-4 w-4" />
          {loading ? "Analyzing..." : "Get AI Explanation"}
        </button>
      </div>

      {limitReached && !isSelected && (
        <div className="mt-3 rounded-lg border border-[var(--accent-200)] bg-[var(--accent-100)]/55 px-4 py-2 text-xs text-[var(--neutral-700)]">
          Compare limit reached (max 3). Remove a case to add a new one.
        </div>
      )}

      {explanation && (
        <motion.div
          className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--surface-alt)] p-4 text-sm leading-6 text-[var(--neutral-700)]"
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          {explanation}
        </motion.div>
      )}
    </motion.article>
  );
}
