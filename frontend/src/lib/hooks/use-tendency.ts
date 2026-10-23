import { useMutation } from "@tanstack/react-query";
import { analyzeOutcomeTendency } from "@/lib/api/tendency";
import type { TendencyRequest } from "@/lib/api/types";

export function useOutcomeTendency() {
  return useMutation({
    mutationFn: (payload: TendencyRequest) => analyzeOutcomeTendency(payload),
  });
}
