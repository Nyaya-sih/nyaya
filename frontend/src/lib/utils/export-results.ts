import type { SearchResponse, SearchResult } from "@/lib/api/types";

function resultToCsvRow(result: SearchResult): string {
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  return [
    result.rank,
    escape(result.case_title),
    escape(result.court),
    escape(result.date_of_judgment),
    escape(result.case_type),
    escape(result.verdict),
    Math.round(result.combined_score * 100),
    escape(result.similarity_explanation),
    escape(result.common_statutes.join("; ")),
    escape(result.sections_invoked.join("; ")),
  ].join(",");
}

const CSV_HEADER =
  "Rank,Case Title,Court,Date,Case Type,Verdict,Score (%),Explanation,Common Statutes,Sections Invoked";

export function exportAsCsv(response: SearchResponse) {
  const rows = [CSV_HEADER, ...response.results.map(resultToCsvRow)];
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, `nyaya-search-results-${timestamp()}.csv`);
}

export function exportAsJson(response: SearchResponse) {
  const blob = new Blob([JSON.stringify(response, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  downloadBlob(blob, `nyaya-search-results-${timestamp()}.json`);
}

function timestamp(): string {
  return new Date().toISOString().slice(0, 19).replace(/[T:]/g, "-");
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
