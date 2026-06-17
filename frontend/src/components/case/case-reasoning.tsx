import type { CaseDetail } from "@/lib/api/types";

export function CaseReasoning({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="legal-panel p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">Court Reasoning</p>
      <p className="mt-3 text-sm leading-6 text-[var(--neutral-700)]">
        {caseDetail.court_reasoning || "Not available"}
      </p>
    </div>
  );
}
