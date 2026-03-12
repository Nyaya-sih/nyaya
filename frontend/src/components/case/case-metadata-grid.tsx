import type { CaseDetail } from "@/lib/api/types";

export function CaseMetadataGrid({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-xs font-semibold text-[var(--neutral-500)]">Classification</p>
        <p className="mt-2 text-sm text-[var(--neutral-700)]">
          Case Type: {caseDetail.case_type || "—"}
        </p>
        <p className="text-sm text-[var(--neutral-700)]">
          Verdict: {caseDetail.verdict || "—"}
        </p>
      </div>
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-xs font-semibold text-[var(--neutral-500)]">Charges & Sections</p>
        <p className="mt-2 text-sm text-[var(--neutral-700)]">
          Charges: {caseDetail.charges.join(", ") || "—"}
        </p>
        <p className="text-sm text-[var(--neutral-700)]">
          Sections: {caseDetail.sections_invoked.join(", ") || "—"}
        </p>
      </div>
    </div>
  );
}
