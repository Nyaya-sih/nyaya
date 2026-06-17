"use client";

import { useRouter } from "next/navigation";

export function FindSimilarButton({ caseId }: { caseId: number }) {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.push(`/results?caseId=${encodeURIComponent(String(caseId))}`)}
      className="legal-button-primary px-4 py-2 text-xs font-semibold"
    >
      Find Similar Cases
    </button>
  );
}
