import { VerdictBadge } from "@/components/shared/verdict-badge";
import { CourtBadge } from "@/components/shared/court-badge";
import { ConfidenceMeter } from "@/components/shared/confidence-meter";
import type { CaseDetail } from "@/lib/api/types";
import { formatDate } from "@/lib/utils/format-date";

export function CaseHeader({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-[var(--primary-900)]">
          {caseDetail.case_title}
        </h1>
        <VerdictBadge verdict={caseDetail.verdict} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-[var(--neutral-600)]">
        <CourtBadge court={caseDetail.court} />
        {caseDetail.date_of_judgment && <span>{formatDate(caseDetail.date_of_judgment)}</span>}
        <span className="font-mono text-xs">Case ID: {caseDetail.case_id}</span>
      </div>
      <div className="mt-4">
        <ConfidenceMeter value={caseDetail.average_confidence} />
      </div>
    </div>
  );
}
