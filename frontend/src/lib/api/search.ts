import { api } from "@/lib/api/client";
import type { SearchResponse, SearchParams, SearchFilters } from "@/lib/api/types";

export async function searchByText(params: SearchParams): Promise<SearchResponse> {
  return api.post<SearchResponse>("/api/v1/cases/similar", params);
}

export async function searchByUpload(
  file: File,
  params: Omit<SearchParams, "text">
): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (params.similarity_mode) formData.append("similarity_mode", params.similarity_mode);
  if (params.top_k) formData.append("top_k", String(params.top_k));
  if (params.court) formData.append("court", params.court);
  if (params.case_type) formData.append("case_type", params.case_type);
  if (params.verdict) formData.append("verdict", params.verdict);
  if (params.year_from !== undefined) formData.append("year_from", String(params.year_from));
  if (params.year_to !== undefined) formData.append("year_to", String(params.year_to));
  return api.postForm<SearchResponse>("/api/v1/cases/similar/upload", formData);
}

export async function getSearchFilters(): Promise<SearchFilters> {
  return api.get<SearchFilters>("/api/v1/cases/search/filters");
}

export async function getAiExplanation(
  queryText: string,
  caseId: number
): Promise<{ explanation: string }> {
  return api.post("/api/v1/cases/explain", {
    query_text: queryText,
    case_id: caseId,
  });
}
