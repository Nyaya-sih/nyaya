import { useMutation } from "@tanstack/react-query";
import {
  createAssistantSession,
  deleteAssistantSession,
  queryAssistant,
} from "@/lib/api/assistant";
import type { AssistantQueryRequest } from "@/lib/api/types";

export function useCreateAssistantSession() {
  return useMutation({
    mutationFn: createAssistantSession,
  });
}

export function useAssistantQuery() {
  return useMutation({
    mutationFn: (payload: AssistantQueryRequest) => queryAssistant(payload),
  });
}

export function useDeleteAssistantSession() {
  return useMutation({
    mutationFn: (sessionId: string) => deleteAssistantSession(sessionId),
  });
}
