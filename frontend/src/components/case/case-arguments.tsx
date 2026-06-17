import type { CaseDetail } from "@/lib/api/types";

export function CaseArguments({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="legal-panel p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">Petitioner Arguments</p>
        <p className="mt-3 text-sm leading-6 text-[var(--neutral-700)]">
          {caseDetail.key_arguments_petitioner || "Not available"}
        </p>
      </div>
      <div className="legal-panel p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">Respondent Arguments</p>
        <p className="mt-3 text-sm leading-6 text-[var(--neutral-700)]">
          {caseDetail.key_arguments_respondent || "Not available"}
        </p>
      </div>
    </div>
  );
}
