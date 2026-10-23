import { api } from "@/lib/api/client";
import type { TendencyRequest, TendencyResponse } from "@/lib/api/types";

export async function analyzeOutcomeTendency(
  payload: TendencyRequest
): Promise<TendencyResponse> {
  return api.post<TendencyResponse>("/api/v1/cases/tendency", payload);
}
