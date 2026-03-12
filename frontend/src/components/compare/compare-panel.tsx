"use client";

import { useCase } from "@/lib/hooks/use-case";
import { useCompareStore, type CompareField } from "@/lib/stores/compare-store";
import { VerdictBadge } from "@/components/shared/verdict-badge";
import { CourtBadge } from "@/components/shared/court-badge";
import { formatDate } from "@/lib/utils/format-date";
import { truncate } from "@/lib/utils/truncate";
import type { CaseDetail } from "@/lib/api/types";

function FieldSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[var(--neutral-500)]">{label}</p>
      <p>{children}</p>
    </div>
  );
}

function renderField(field: CompareField, data: CaseDetail) {
  switch (field) {
    case "Parties":
      return (
        <FieldSection label="Parties">
          {[data.key_arguments_petitioner ? "Petitioner" : null, data.key_arguments_respondent ? "Respondent" : null]
            .filter(Boolean)
            .join(" vs ") || "—"}
        </FieldSection>
      );
    case "Charges":
      return (
        <>
          <FieldSection label="Charges">{data.charges.join(", ") || "—"}</FieldSection>
          <FieldSection label="Sections Invoked">{data.sections_invoked.join(", ") || "—"}</FieldSection>
        </>
      );
    case "Verdict":
      return (
        <FieldSection label="Verdict">
          <VerdictBadge verdict={data.verdict} />
        </FieldSection>
      );
    case "Statutes":
      return <FieldSection label="Statutes Cited">{data.statutes_cited.join(", ") || "—"}</FieldSection>;
    case "Arguments":
      return (
        <>
          <FieldSection label="Petitioner Arguments">
            {truncate(data.key_arguments_petitioner || "", 180) || "—"}
          </FieldSection>
          <FieldSection label="Respondent Arguments">
            {truncate(data.key_arguments_respondent || "", 180) || "—"}
          </FieldSection>
        </>
      );
    case "Reasoning":
      return (
        <FieldSection label="Court Reasoning">
          {truncate(data.court_reasoning || "", 200) || "—"}
        </FieldSection>
      );
    default:
      return null;
  }
}

export function ComparePanel({ caseId }: { caseId: string }) {
  const { data } = useCase(caseId);
  const visibleFields = useCompareStore((state) => state.visibleFields);

  if (!data) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--neutral-500)]">
        Loading {caseId}...
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="text-lg font-semibold text-[var(--primary-900)]">{data.case_title}</h3>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-[var(--neutral-500)]">
        <CourtBadge court={data.court} />
        {data.date_of_judgment && <span>{formatDate(data.date_of_judgment)}</span>}
        <VerdictBadge verdict={data.verdict} />
      </div>
      <div className="mt-4 space-y-3 text-xs text-[var(--neutral-600)]">
        <FieldSection label="Case Type">{data.case_type || "—"}</FieldSection>
        {visibleFields.map((field) => (
          <div key={field}>{renderField(field, data)}</div>
        ))}
      </div>
    </div>
  );
}
