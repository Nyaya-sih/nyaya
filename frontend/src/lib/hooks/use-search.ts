import { useMutation, useQuery } from "@tanstack/react-query";
import { searchByText, searchByUpload, getSearchFilters } from "@/lib/api/search";
import type { SearchParams } from "@/lib/api/types";

export function useSearchByText() {
  return useMutation({
    mutationFn: (params: SearchParams) => searchByText(params),
  });
}

export function useSearchByUpload() {
  return useMutation({
    mutationFn: ({ file, params }: { file: File; params: SearchParams }) =>
      searchByUpload(file, params),
  });
}

export function useSearchFilters() {
  return useQuery({
    queryKey: ["search-filters"],
    queryFn: getSearchFilters,
    staleTime: 1000 * 60 * 30,
  });
}
