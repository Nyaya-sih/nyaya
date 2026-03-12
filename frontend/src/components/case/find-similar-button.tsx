"use client";

import { useRouter } from "next/navigation";

export function FindSimilarButton({ caseId }: { caseId: number }) {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.push(`/results?caseId=${encodeURIComponent(String(caseId))}`)}
      className="rounded-full bg-[var(--primary-700)] px-4 py-2 text-xs font-semibold text-white"
    >
      Find Similar Cases
    </button>
  );
}
