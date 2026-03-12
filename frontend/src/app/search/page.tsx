"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Container } from "@/components/layout/container";
import { SearchModeToggle } from "@/components/search/search-mode-toggle";
import { FileUploadZone } from "@/components/search/file-upload-zone";
import { TextSearchInput } from "@/components/search/text-search-input";
import { SearchFilters } from "@/components/search/search-filters";
import { SearchHistory } from "@/components/search/search-history";
import { useSearchStore } from "@/lib/stores/search-store";
import { useSearchByText, useSearchByUpload } from "@/lib/hooks/use-search";
import type { SearchParams } from "@/lib/api/types";

export default function SearchPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const searchMode = useSearchStore((state) => state.searchMode);
  const queryText = useSearchStore((state) => state.queryText);
  const uploadedFile = useSearchStore((state) => state.uploadedFile);
  const similarityMode = useSearchStore((state) => state.similarityMode);
  const topK = useSearchStore((state) => state.topK);
  const filters = useSearchStore((state) => state.filters);
  const addRecentSearch = useSearchStore((state) => state.addRecentSearch);
  const setResponseForId = useSearchStore((state) => state.setResponseForId);

  const textSearch = useSearchByText();
  const uploadSearch = useSearchByUpload();

  const isReady = searchMode === "upload" ? Boolean(uploadedFile) : queryText.trim().length >= 100;

  const handleSearch = async () => {
    if (!isReady) return;
    setError(null);
    const searchKey = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`;
    const params: SearchParams = {
      text: searchMode === "text" ? queryText.trim() : undefined,
      similarity_mode: similarityMode,
      top_k: topK,
      court: filters.courts[0],
      case_type: filters.caseTypes[0],
      verdict: filters.verdicts[0],
      year_from: filters.yearMin ?? undefined,
      year_to: filters.yearMax ?? undefined,
    };

    try {
      const response =
        searchMode === "upload" && uploadedFile
          ? await uploadSearch.mutateAsync({ file: uploadedFile, params })
          : await textSearch.mutateAsync(params);
      sessionStorage.setItem(`search:${searchKey}`, JSON.stringify(response));
      sessionStorage.setItem("search:last", searchKey);
      setResponseForId(searchKey, response);
      addRecentSearch({ query: response.query_summary, resultCount: response.total_results });
      const query = new URLSearchParams({ mode: similarityMode, sid: searchKey });
      if (searchMode === "text") query.set("q", queryText.trim());
      router.push(`/results?${query.toString()}`);
    } catch {
      setError("Search failed. Please try again.");
    }
  };

  return (
    <div>
      <PageHeader
        title="Search Similar Cases"
        breadcrumb={[{ label: "Home", href: "/" }, { label: "Search" }]}
        description="Upload a case document or paste text to retrieve relevant precedents."
      />
      <Container className="space-y-8 pb-20">
        <SearchModeToggle />

        {searchMode === "upload" ? <FileUploadZone /> : <TextSearchInput />}

        <SearchFilters />

        <button
          type="button"
          onClick={handleSearch}
          disabled={!isReady || textSearch.isPending || uploadSearch.isPending}
          className={`w-full rounded-full py-3 text-sm font-semibold transition ${
            isReady
              ? "bg-[var(--primary-700)] text-white"
              : "bg-[var(--surface-alt)] text-[var(--neutral-400)]"
          }`}
        >
          {textSearch.isPending || uploadSearch.isPending ? "Searching..." : "Search Similar Cases"}
        </button>

        {error && <p className="text-sm text-[var(--danger)]">{error}</p>}

        <SearchHistory />
      </Container>
    </div>
  );
}
