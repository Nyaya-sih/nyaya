"use client";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { useCompareStore } from "@/lib/stores/compare-store";
import { ComparePanel } from "@/components/compare/compare-panel";
import { CompareToolbar } from "@/components/compare/compare-toolbar";

export default function ComparePage() {
  const selectedCaseIds = useCompareStore((state) => state.selectedCaseIds);
  const clearAll = useCompareStore((state) => state.clearAll);

  return (
    <div>
      <PageHeader
        title="Compare Cases"
        breadcrumb={[{ label: "Home", href: "/" }, { label: "Compare" }]}
        description="Review selected cases side-by-side with shared fields highlighted."
      />
      <Container className="space-y-6 pb-20">
        <div className="flex items-center justify-between">
          <p className="text-sm text-[var(--neutral-600)]">
            {selectedCaseIds.length} cases selected
          </p>
          <button
            type="button"
            onClick={clearAll}
            className="text-xs text-[var(--neutral-500)]"
          >
            Clear all
          </button>
        </div>
        <CompareToolbar />
        <div className="grid gap-4 md:grid-cols-2">
          {selectedCaseIds.map((caseId) => (
            <ComparePanel key={caseId} caseId={caseId} />
          ))}
          {selectedCaseIds.length === 0 && (
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 text-sm text-[var(--neutral-500)]">
              Select cases from the results page to compare.
            </div>
          )}
        </div>
      </Container>
    </div>
  );
}
