import { useMutation, useQuery } from "@tanstack/react-query";
import {
  cancelCourtroomAnalysis,
  createCourtroomAnalysis,
  getCourtroomAnalysis,
  getCourtroomStatus,
} from "@/lib/api/courtroom";
import type { CourtroomAnalyzeRequest } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

export function useCreateCourtroomAnalysis() {
  return useMutation({
    mutationFn: (payload: CourtroomAnalyzeRequest) => createCourtroomAnalysis(payload),
  });
}

export function useCourtroomAnalysis(analysisId: string) {
  return useQuery({
    queryKey: ["courtroom-analysis", analysisId],
    queryFn: () => getCourtroomAnalysis(analysisId),
    enabled: Boolean(analysisId),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    refetchInterval: (query) => {
      if (query.state.error instanceof ApiError && query.state.error.status === 404) return false;
      const status = query.state.data?.status;
      return !status || status === "running" || status === "queued" ? 1500 : false;
    },
  });
}

export function useCourtroomStatus(analysisId: string, enabled = true) {
  return useQuery({
    queryKey: ["courtroom-status", analysisId],
    queryFn: () => getCourtroomStatus(analysisId),
    enabled: Boolean(analysisId) && enabled,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
    refetchInterval: (query) => {
      if (query.state.error instanceof ApiError && query.state.error.status === 404) return false;
      const status = query.state.data?.status;
      if (!status || status === "running" || status === "queued") {
        return 1500;
      }
      return false;
    },
  });
}

export function useCancelCourtroomAnalysis() {
  return useMutation({
    mutationFn: (analysisId: string) => cancelCourtroomAnalysis(analysisId),
  });
}
