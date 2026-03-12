"use client";

import { useParams } from "next/navigation";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { useCase } from "@/lib/hooks/use-case";
import { CaseHeader } from "@/components/case/case-header";
import { CaseMetadataGrid } from "@/components/case/case-metadata-grid";
import { CaseArguments } from "@/components/case/case-arguments";
import { CaseReasoning } from "@/components/case/case-reasoning";
import { CaseStatutes } from "@/components/case/case-statutes";
import { CasePrecedents } from "@/components/case/case-precedents";
import { CaseFullText } from "@/components/case/case-full-text";
import { CaseConfidence } from "@/components/case/case-confidence";
import { FindSimilarButton } from "@/components/case/find-similar-button";

export default function CaseDetailPage() {
  const params = useParams();
  const caseId = typeof params?.id === "string" ? params.id : "";
  const { data, isLoading } = useCase(caseId);

  if (isLoading) {
    return (
      <Container className="py-10 text-sm text-[var(--neutral-500)]">
        Loading case details...
      </Container>
    );
  }

  if (!data) {
    return (
      <Container className="py-10 text-sm text-[var(--neutral-500)]">
        Case not found.
      </Container>
    );
  }

  return (
    <div>
      <PageHeader
        title="Case Detail"
        breadcrumb={[
          { label: "Home", href: "/" },
          { label: "Search", href: "/search" },
          { label: "Case Detail" },
        ]}
      />
      <Container className="space-y-6 pb-20">
        <CaseHeader caseDetail={data} />
        <div className="flex flex-wrap items-center gap-3">
          <FindSimilarButton caseId={data.case_id} />
          <span className="text-xs text-[var(--neutral-500)]">Validation: {data.validation_status}</span>
        </div>
        <CaseMetadataGrid caseDetail={data} />
        <CaseArguments caseDetail={data} />
        <CaseReasoning caseDetail={data} />
        <div className="grid gap-4 md:grid-cols-2">
          <CaseStatutes caseDetail={data} />
          <CasePrecedents caseDetail={data} />
        </div>
        <CaseConfidence caseDetail={data} />
        <CaseFullText caseDetail={data} />
      </Container>
    </div>
  );
}
