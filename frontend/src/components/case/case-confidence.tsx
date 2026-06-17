import type { CaseDetail } from "@/lib/api/types";

export function CaseConfidence({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="legal-panel p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">Extraction Confidence</p>
      <div className="mt-3 text-xs text-[var(--neutral-600)]">
        Average confidence: {Math.round(caseDetail.average_confidence * 100)}%
      </div>
    </div>
  );
}
