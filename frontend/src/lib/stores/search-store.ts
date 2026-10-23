import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { SearchResponse } from "@/lib/api/types";

export type SearchMode = "text" | "upload";
export type SimilarityMode = "combined" | "factual" | "legal" | "fulltext";

interface SearchFiltersState {
  courts: string[];
  caseTypes: string[];
  verdicts: string[];
  yearMin: number | null;
  yearMax: number | null;
}

interface SearchState {
  searchMode: SearchMode;
  queryText: string;
  uploadedFile: File | null;
  similarityMode: SimilarityMode;
  topK: number;
  filters: SearchFiltersState;
  recentSearches: Array<{ query: string; timestamp: number; resultCount: number }>;
  responsesById: Record<string, SearchResponse>;
  setSearchMode: (mode: SearchMode) => void;
  setQueryText: (text: string) => void;
  setUploadedFile: (file: File | null) => void;
  setSimilarityMode: (mode: SimilarityMode) => void;
  setTopK: (k: number) => void;
  updateFilters: (partial: Partial<SearchFiltersState>) => void;
  clearFilters: () => void;
  addRecentSearch: (search: { query: string; resultCount: number }) => void;
  setResponseForId: (id: string, response: SearchResponse) => void;
  clearResponseForId: (id: string) => void;
}

const defaultFilters: SearchFiltersState = {
  courts: [],
  caseTypes: [],
  verdicts: [],
  yearMin: null,
  yearMax: null,
};

export const useSearchStore = create<SearchState>()(
  persist(
    (set) => ({
      searchMode: "upload",
      queryText: "",
      uploadedFile: null,
      similarityMode: "combined",
      topK: 10,
      filters: defaultFilters,
      recentSearches: [],
      responsesById: {},
      setSearchMode: (mode) => set({ searchMode: mode }),
      setQueryText: (text) => set({ queryText: text }),
      setUploadedFile: (file) => set({ uploadedFile: file }),
      setSimilarityMode: (mode) => set({ similarityMode: mode }),
      setTopK: (k) => set({ topK: k }),
      updateFilters: (partial) =>
        set((state) => ({ filters: { ...state.filters, ...partial } })),
      clearFilters: () => set({ filters: defaultFilters }),
      addRecentSearch: (search) =>
        set((state) => ({
          recentSearches: [
            { query: search.query, resultCount: search.resultCount, timestamp: Date.now() },
            ...state.recentSearches,
          ].slice(0, 6),
        })),
      setResponseForId: (id, response) =>
        set((state) => ({
          responsesById: { ...state.responsesById, [id]: response },
        })),
      clearResponseForId: (id) =>
        set((state) => {
          const next = { ...state.responsesById };
          delete next[id];
          return { responsesById: next };
        }),
    }),
    {
      name: "nyaya-search",
      partialize: (state) => ({
        searchMode: state.searchMode,
        queryText: state.queryText,
        similarityMode: state.similarityMode,
        topK: state.topK,
        filters: state.filters,
        recentSearches: state.recentSearches,
      }),
    }
  )
);
