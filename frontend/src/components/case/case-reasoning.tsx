import type { CaseDetail } from "@/lib/api/types";

export function CaseReasoning({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-semibold text-[var(--neutral-500)]">Court Reasoning</p>
      <p className="mt-3 text-sm text-[var(--neutral-700)]">
        {caseDetail.court_reasoning || "Not available"}
      </p>
    </div>
  );
}
