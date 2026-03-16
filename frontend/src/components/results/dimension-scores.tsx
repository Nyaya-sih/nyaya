import type { SimilarityDimension } from "@/lib/api/types";

interface DimensionScoresProps {
  scores: SimilarityDimension[];
  semanticScore?: number;
}

function aggregateScores(scores: SimilarityDimension[], semanticScore?: number) {
  const byName = new Map(scores.map((item) => [item.name.toLowerCase(), item.score]));
  const statutory = byName.get("statutory") ?? 0;
  const caseType = byName.get("case type") ?? 0;
  const court = byName.get("court") ?? 0;
  const temporal = byName.get("temporal") ?? 0;
  const outcome = byName.get("outcome") ?? 0;

  return [
    {
      name: "Semantic Match",
      score: Math.max(0, Math.min(1, semanticScore ?? (0.55 * statutory + 0.45 * caseType))),
    },
    {
      name: "Legal Overlap",
      score: Math.max(0, Math.min(1, 0.75 * statutory + 0.25 * caseType)),
    },
    {
      name: "Context Match",
      score: Math.max(0, Math.min(1, 0.55 * court + 0.35 * temporal + 0.1 * outcome)),
    },
  ];
}

export function DimensionScores({ scores, semanticScore }: DimensionScoresProps) {
  const aggregated = aggregateScores(scores, semanticScore);
  return (
    <div className="space-y-2 text-xs">
      {aggregated.map((dimension) => (
        <div key={dimension.name} className="flex items-center gap-3">
          <span className="w-28 text-[var(--neutral-500)]">{dimension.name}</span>
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
