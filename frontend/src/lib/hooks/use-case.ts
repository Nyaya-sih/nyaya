import { useQuery } from "@tanstack/react-query";
import { getCaseById } from "@/lib/api/cases";

export function useCase(caseId: string) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCaseById(caseId),
    enabled: Boolean(caseId),
    staleTime: 1000 * 60 * 60,
  });
}
