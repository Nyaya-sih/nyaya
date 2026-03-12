import type { CaseDetail } from "@/lib/api/types";

export function CaseStatutes({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-semibold text-[var(--neutral-500)]">Statutes Cited</p>
      <ul className="mt-3 space-y-2 text-sm text-[var(--neutral-700)]">
        {caseDetail.statutes_cited.length ? (
          caseDetail.statutes_cited.map((statute) => (
            <li key={statute}>{statute}</li>
          ))
        ) : (
          <li>Not available</li>
        )}
      </ul>
    </div>
  );
}
