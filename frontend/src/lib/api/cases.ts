import { api } from "@/lib/api/client";
import type { CaseDetail, SearchResponse } from "@/lib/api/types";

export async function getCaseById(caseId: string): Promise<CaseDetail> {
  return api.get<CaseDetail>(`/api/v1/cases/${encodeURIComponent(caseId)}`);
}

export async function getSimilarCases(caseId: string): Promise<SearchResponse> {
  return api.get<SearchResponse>(
    `/api/v1/cases/${encodeURIComponent(caseId)}/similar`
  );
}
