import type { SimilarityDimension } from "@/lib/api/types";

interface DimensionScoresProps {
  scores: SimilarityDimension[];
}

export function DimensionScores({ scores }: DimensionScoresProps) {
  return (
    <div className="space-y-2 text-xs">
      {scores.map((dimension) => (
        <div key={dimension.name} className="flex items-center gap-3">
          <span className="w-24 capitalize text-[var(--neutral-500)]">{dimension.name}</span>
          <div className="h-2 flex-1 rounded-full bg-[var(--surface-alt)]">
            <div
              className="h-full rounded-full bg-[var(--primary-500)]"
              style={{ width: `${Math.round(dimension.score * 100)}%` }}
            />
          </div>
          <span className="w-10 text-right text-[var(--neutral-600)]">
            {Math.round(dimension.score * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}
