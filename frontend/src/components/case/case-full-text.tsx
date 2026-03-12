"use client";

import { useState } from "react";
import type { CaseDetail } from "@/lib/api/types";

export function CaseFullText({ caseDetail }: { caseDetail: CaseDetail }) {
  const [expanded, setExpanded] = useState(false);
  const content = expanded ? caseDetail.full_text : caseDetail.full_text.slice(0, 1200);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <p className="text-xs font-semibold text-[var(--neutral-500)]">Full Judgment Text</p>
      <pre className="mt-3 max-h-[480px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-[var(--surface-alt)] p-3 text-xs text-[var(--neutral-700)]">
        {content}
      </pre>
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="mt-3 text-xs text-[var(--primary-700)]"
      >
        {expanded ? "Show less" : "Show full text"}
      </button>
    </div>
  );
}
