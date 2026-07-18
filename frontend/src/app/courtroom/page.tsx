"use client";

import { useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import {
  useCancelCourtroomAnalysis,
  useCourtroomAnalysis,
  useCourtroomStatus,
  useCreateCourtroomAnalysis,
} from "@/lib/hooks/use-courtroom";
import type { CourtroomMode } from "@/lib/api/types";
import { useCourtroomEvents } from "@/lib/hooks/use-courtroom-events";
import { staggerContainer, staggerItem } from "@/lib/utils/motion";

export default function CourtroomPage() {
  const reduceMotion = useReducedMotion();
  const [mode, setMode] = useState<CourtroomMode>("quick");
  const [includeRebuttal, setIncludeRebuttal] = useState(false);
  const [caseText, setCaseText] = useState("");
  const [analysisId, setAnalysisId] = useState("");

  const create = useCreateCourtroomAnalysis();
  const cancel = useCancelCourtroomAnalysis();
  const status = useCourtroomStatus(analysisId, Boolean(analysisId));
  const analysis = useCourtroomAnalysis(analysisId);
  const courtroomEvents = useCourtroomEvents(analysisId);

  const isRunning = useMemo(() => {
    const s = status.data?.status;
    return s === "queued" || s === "running";
  }, [status.data?.status]);

  const handleAnalyze = () => {
    if (caseText.trim().length < 60) return;
    create.mutate(
      {
        mode,
        include_rebuttal: mode === "full" ? includeRebuttal : false,
        source_type: "text",
        case_text: caseText,
        top_k_legal: 8,
        top_k_cases: 0,
      },
      {
        onSuccess: (res) => {
          setAnalysisId(res.analysis_id);
        },
      }
    );
  };

  const handleCancel = () => {
    if (!analysisId) return;
    cancel.mutate(analysisId);
  };

  return (
    <div>
      <PageHeader
        title="Simulated Courtroom"
        breadcrumb={[{ label: "Home", href: "/" }, { label: "Courtroom" }]}
        description="Multi-role deliberation engine with peer scoring, rebuttal, and judge synthesis."
      />

      <Container className="space-y-6 pb-16">
        <motion.div
          className="space-y-6"
          variants={staggerContainer}
          initial={reduceMotion ? false : "initial"}
          animate={reduceMotion ? undefined : "animate"}
        >
        <motion.div variants={staggerItem} className="legal-panel p-5">
          <p className="text-xs uppercase text-[var(--neutral-500)]">Input</p>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <label className="text-sm text-[var(--neutral-700)]">
              Mode
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as CourtroomMode)}
                className="ml-2 rounded-lg border border-[var(--border)] bg-white px-2 py-1 text-sm"
              >
                <option value="quick">Quick</option>
                <option value="full">Full</option>
              </select>
            </label>

            <label className="flex items-center gap-2 text-sm text-[var(--neutral-700)]">
              <input
                type="checkbox"
                checked={includeRebuttal}
                onChange={(e) => setIncludeRebuttal(e.target.checked)}
                disabled={mode !== "full"}
              />
              Include rebuttal round
            </label>
          </div>

          <textarea
            value={caseText}
            onChange={(e) => setCaseText(e.target.value)}
            placeholder="Paste case facts, issues, and procedural posture..."
            className="mt-4 min-h-[220px] w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
          />

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={create.isPending || caseText.trim().length < 60}
              className="legal-button-primary px-5 py-2 text-sm font-semibold disabled:opacity-60"
            >
              {create.isPending ? "Starting..." : "Run Courtroom Analysis"}
            </button>

            <button
              type="button"
              onClick={handleCancel}
              disabled={!analysisId || !isRunning}
              className="legal-button-secondary px-5 py-2 text-sm disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </motion.div>

        {analysisId && (
          <motion.div variants={staggerItem} className="legal-panel p-5">
            <p className="text-xs uppercase text-[var(--neutral-500)]">Run Status</p>
            <p className="mt-2 text-sm text-[var(--neutral-700)]">
              Analysis ID: {analysisId}
            </p>
            <p className="text-sm text-[var(--neutral-700)]">
              {status.data
                ? `Status: ${status.data.status} | Stage: ${status.data.stage} | Progress: ${status.data.progress_percent}%`
                : "Loading status..."}
            </p>
          </motion.div>
        )}

        {analysis.data && (
          <>
            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Executive Summary</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--neutral-800)]">
                {analysis.data.synthesis.executive_summary}
              </p>
              <p className="mt-3 text-sm text-[var(--neutral-800)]">
                Recommendation: {analysis.data.synthesis.recommended_outcome}
              </p>
              <p className="mt-2 text-xs text-[var(--neutral-500)]">
                Confidence {analysis.data.synthesis.confidence.toFixed(2)} | Consensus{" "}
                {analysis.data.transparency_dashboard.consensus_meter.toFixed(2)} | Cost $ 
                {analysis.data.transparency_dashboard.estimated_cost_usd.toFixed(4)}
              </p>
            </motion.div>

            <motion.div variants={staggerItem} className="legal-panel p-5">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase text-[var(--neutral-500)]">Live Transcript</p>
                <p className="text-xs text-[var(--neutral-500)]">
                  {courtroomEvents.isConnected ? "Connected" : "Replaying"} | {courtroomEvents.events.length} events
                </p>
              </div>
              {courtroomEvents.error && (
                <p className="mt-2 text-xs text-red-600">{courtroomEvents.error}</p>
              )}
              <div className="mt-3 max-h-[420px] space-y-3 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
                {courtroomEvents.events.map((event) => (
                  <div key={event.event_id} className="rounded-lg border border-[var(--border)] bg-white p-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--neutral-500)]">
                      <span className="font-semibold text-[var(--primary-900)]">{event.role}</span>
                      <span>{event.stage}</span>
                      <span>{event.event_type}</span>
                      <span>R{event.round}</span>
                      <span>{event.model_provider}/{event.model_id}</span>
                      <span>conf {event.confidence.toFixed(2)}</span>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--neutral-800)]">
                      {event.content}
                    </p>
                    {event.citations.length > 0 && (
                      <p className="mt-2 text-xs text-[var(--neutral-500)]">
                        Citations: {event.citations.map((citation) => citation.section_ref).join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Role Analyses</p>
              <div className="mt-3 space-y-4">
                {analysis.data.role_analyses.map((role) => (
                  <div key={role.role_name} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
                    <p className="text-sm font-semibold text-[var(--primary-900)]">
                      {role.role_name}
                    </p>
                    <p className="mt-1 text-xs text-[var(--neutral-500)]">
                      {role.provider || "n/a"} / {role.model || "n/a"} | confidence {role.confidence.toFixed(2)}
                      {role.degraded ? " | degraded" : ""}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--neutral-800)]">
                      {role.analysis_text}
                    </p>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div variants={staggerItem} className="legal-panel p-5">
              <p className="text-xs uppercase text-[var(--neutral-500)]">Warnings</p>
              <ul className="mt-2 space-y-1 text-sm text-[var(--neutral-700)]">
                {analysis.data.warnings.map((w, idx) => (
                  <li key={`${idx}-${w.slice(0, 30)}`}>- {w}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-[var(--neutral-500)]">{analysis.data.disclaimer}</p>
            </motion.div>
          </>
        )}
        </motion.div>
      </Container>
    </div>
  );
}
