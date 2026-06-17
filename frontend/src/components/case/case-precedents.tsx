import type { CaseDetail } from "@/lib/api/types";

export function CasePrecedents({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="legal-panel p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[var(--neutral-500)]">Precedents Cited</p>
      <ul className="mt-3 space-y-2 text-sm text-[var(--neutral-700)]">
        {caseDetail.precedents_cited.length ? (
          caseDetail.precedents_cited.map((precedent) => (
            <li key={precedent.case_name}>
              {precedent.case_name}
              {precedent.year ? ` (${precedent.year})` : ""}
            </li>
          ))
        ) : (
          <li>Not available</li>
        )}
      </ul>
    </div>
  );
}
