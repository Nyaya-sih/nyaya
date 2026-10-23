import { api } from "@/lib/api/client";
import type {
  AssistantDeleteResponse,
  AssistantQueryRequest,
  AssistantQueryResponse,
  AssistantSessionResponse,
} from "@/lib/api/types";

export async function createAssistantSession(): Promise<AssistantSessionResponse> {
  return api.post<AssistantSessionResponse>("/api/v1/assistant/session", {});
}

export async function queryAssistant(
  payload: AssistantQueryRequest
): Promise<AssistantQueryResponse> {
  return api.post<AssistantQueryResponse>("/api/v1/assistant/query", payload);
}

export async function deleteAssistantSession(
  sessionId: string
): Promise<AssistantDeleteResponse> {
  return api.delete<AssistantDeleteResponse>(`/api/v1/assistant/session/${sessionId}`);
}
