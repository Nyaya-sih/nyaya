import { api } from "@/lib/api/client";
import type {
  CourtroomAnalysisResponse,
  CourtroomAnalyzeRequest,
  CourtroomCancelResponse,
  CourtroomCreateResponse,
  CourtroomTrialEvent,
  CourtroomStatusResponse,
  CourtroomDocument,
} from "@/lib/api/types";

export async function extractCourtroomDocument(file: File): Promise<CourtroomDocument> {
  const body = new FormData();
  body.append("file", file);
  return api.postForm("/api/v1/courtroom/document", body);
}

export function getCourtroomReportPdf(analysisId: string): Promise<Blob> {
  return api.getBlob(`/api/v1/courtroom/analysis/${encodeURIComponent(analysisId)}/report.pdf`);
}

export async function createCourtroomAnalysis(
  payload: CourtroomAnalyzeRequest
): Promise<CourtroomCreateResponse> {
  return api.post<CourtroomCreateResponse>("/api/v1/courtroom/analyze", payload);
}

export async function getCourtroomAnalysis(
  analysisId: string
): Promise<CourtroomAnalysisResponse> {
  return api.get<CourtroomAnalysisResponse>(`/api/v1/courtroom/analysis/${analysisId}`);
}

export async function getCourtroomStatus(
  analysisId: string
): Promise<CourtroomStatusResponse> {
  return api.get<CourtroomStatusResponse>(
    `/api/v1/courtroom/analysis/${analysisId}/status`
  );
}

export async function cancelCourtroomAnalysis(
  analysisId: string
): Promise<CourtroomCancelResponse> {
  return api.post<CourtroomCancelResponse>(
    `/api/v1/courtroom/analysis/${analysisId}/cancel`,
    {}
  );
}

export async function getCourtroomEvents(
  analysisId: string
): Promise<CourtroomTrialEvent[]> {
  return api.get<CourtroomTrialEvent[]>(`/api/v1/courtroom/analysis/${analysisId}/events`);
}
