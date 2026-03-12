import type { CaseDetail } from "@/lib/api/types";

export function CaseConfidence({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-semibold text-[var(--neutral-500)]">Extraction Confidence</p>
      <div className="mt-3 text-xs text-[var(--neutral-600)]">
        Average confidence: {Math.round(caseDetail.average_confidence * 100)}%
      </div>
    </div>
  );
}
