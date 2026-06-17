"use client";

import { useMemo, useState } from "react";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { useOutcomeTendency } from "@/lib/hooks/use-tendency";
import { motion, useReducedMotion } from "framer-motion";
import { staggerContainer, staggerItem } from "@/lib/utils/motion";

export default function TendencyPage() {
  const reduceMotion = useReducedMotion();
  const [sourceType, setSourceType] = useState<"text" | "case_id">("text");
  const [caseText, setCaseText] = useState("");
  const [caseId, setCaseId] = useState("");
  const [topK, setTopK] = useState(300);
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");

  const tendency = useOutcomeTendency();

  const isReady = useMemo(() => {
    if (sourceType === "text") {
      return caseText.trim().length >= 80;
    }
    const n = Number(caseId);
    return Number.isInteger(n) && n > 0;
  }, [sourceType, caseText, caseId]);

  const handleAnalyze = () => {
    if (!isReady) return;
    tendency.mutate({
      mode: "baseline",
      source_type: sourceType,
      case_text: sourceType === "text" ? caseText : undefined,
      case_id: sourceType === "case_id" ? Number(caseId) : undefined,
      top_k_similar: topK,
      year_from: yearFrom ? Number(yearFrom) : undefined,
      year_to: yearTo ? Number(yearTo) : undefined,
    });
  };

  const report = tendency.data;

  return (
    <div>
      <PageHeader
        title="Outcome Tendency"
        breadcrumb={[{ label: "Home", href: "/" }, { label: "Tendency" }]}
        description="Historical pattern analysis over similar cases with confidence, caveats, and bias checks."
      />

      <Container className="space-y-6 pb-20">
        <motion.div
          variants={staggerContainer}
          initial={reduceMotion ? false : "initial"}
          animate={reduceMotion ? undefined : "animate"}
          className="space-y-6"
        >
        <motion.div variants={staggerItem} className="legal-panel p-5">
          <p className="text-xs uppercase text-[var(--neutral-500)]">Input</p>

          <div className="mt-3 flex flex-wrap items-center gap-4 text-sm text-[var(--neutral-700)]">
            <label>
              Source
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value as "text" | "case_id")}
                className="ml-2 rounded-lg border border-[var(--border)] bg-white px-2 py-1"
              >
                <option value="text">Case text</option>
                <option value="case_id">Case ID</option>
              </select>
            </label>

            <label>
              Top K
              <input
                type="number"
                min={50}
                max={2000}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value) || 300)}
                className="ml-2 w-24 rounded-lg border border-[var(--border)] px-2 py-1"
              />
            </label>

            <label>
              Year from
              <input
                type="number"
                min={1950}
                max={2100}
                value={yearFrom}
                onChange={(e) => setYearFrom(e.target.value)}
                className="ml-2 w-24 rounded-lg border border-[var(--border)] px-2 py-1"
              />
            </label>

            <label>
              Year to
              <input
                type="number"
                min={1950}
                max={2100}
                value={yearTo}
                onChange={(e) => setYearTo(e.target.value)}
                className="ml-2 w-24 rounded-lg border border-[var(--border)] px-2 py-1"
              />
            </label>
          </div>

          {sourceType === "text" ? (
            <textarea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              placeholder="Paste case facts, issues, and procedural context for tendency analysis..."
              className="mt-4 min-h-[200px] w-full rounded-xl border border-[var(--border)] p-3 text-sm"
            />
          ) : (
            <input
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="Enter case id (e.g., 42)"
              className="mt-4 w-full rounded-xl border border-[var(--border)] p-3 text-sm"
            />
          )}

          <button
            type="button"
            onClick={handleAnalyze}
            disabled={!isReady || tendency.isPending}
            className="legal-button-primary mt-4 px-5 py-2 text-sm font-semibold disabled:opacity-60"
          >
            {tendency.isPending ? "Analyzing..." : "Run Tendency Analysis"}
          </button>
        </motion.div>

        {report && (
          <>
            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Summary</p>
              <p className="mt-2 text-sm text-[var(--neutral-800)]">{report.summary_text}</p>
              <p className="mt-2 text-xs text-[var(--neutral-500)]">
                Sample size: {report.sample_size} | Confidence: {report.confidence_band.level} (
                {(report.confidence_band.reliability_score * 100).toFixed(1)}% reliability)
              </p>
            </motion.div>

            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Outcome Distribution</p>
              <div className="mt-3 space-y-3">
                {report.outcome_distribution.map((bucket) => (
                  <div key={bucket.label}>
                    <div className="flex items-center justify-between text-sm text-[var(--neutral-800)]">
                      <span>{bucket.label}</span>
                      <span>
                        {bucket.percentage.toFixed(1)}% ({bucket.count})
                      </span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-[var(--surface-alt)]">
                      <motion.div
                        className="h-2 rounded-full bg-[var(--primary-700)]"
                        style={{ originX: 0 }}
                        initial={reduceMotion ? false : { scaleX: 0 }}
                        animate={reduceMotion ? undefined : { scaleX: Math.min(1, Math.max(0, bucket.percentage / 100)) }}
                        transition={{ duration: 0.35, ease: "easeOut" }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            <div className="grid gap-6 md:grid-cols-2">
              <motion.div variants={staggerItem} className="legal-panel p-5">
                <p className="text-xs uppercase text-[var(--neutral-500)]">Explainability</p>
                <ul className="mt-3 space-y-2 text-sm text-[var(--neutral-800)]">
                  {report.explainability_signals.map((item) => (
                    <li key={`${item.factor}-${item.influence_percent}`}>
                      {item.factor} ({item.influence_percent.toFixed(1)}%): {item.evidence_note}
                    </li>
                  ))}
                </ul>
              </motion.div>

              <motion.div variants={staggerItem} className="legal-panel p-5">
                <p className="text-xs uppercase text-[var(--neutral-500)]">Bias Audit</p>
                <p className="mt-2 text-sm text-[var(--neutral-800)]">
                  Disparity: {report.bias_audit.disparity_flag ? "Flagged" : "Clear"} | Drift: {report.bias_audit.drift_flag ? "Flagged" : "Clear"}
                </p>
                <p className="text-sm text-[var(--neutral-700)]">
                  Max slice gap: {report.bias_audit.max_slice_gap_percent.toFixed(1)}%
                </p>
                <ul className="mt-2 space-y-1 text-sm text-[var(--neutral-700)]">
                  {report.bias_audit.notes.map((note, idx) => (
                    <li key={`${idx}-${note.slice(0, 20)}`}>- {note}</li>
                  ))}
                </ul>
              </motion.div>
            </div>

            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Warnings & Caveats</p>
              <ul className="mt-2 space-y-1 text-sm text-[var(--neutral-700)]">
                {[...report.warnings, ...report.limitations].map((text, idx) => (
                  <li key={`${idx}-${text.slice(0, 24)}`}>- {text}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-[var(--neutral-500)]">{report.disclaimer}</p>
            </motion.div>
          </>
        )}
        </motion.div>
      </Container>
    </div>
  );
}
