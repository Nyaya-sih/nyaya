import { cn } from "@/lib/utils/cn";

export function ConfidenceMeter({ value, className }: { value: number; className?: string }) {
  const percentage = Math.round(value * 100);
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="h-2 w-28 overflow-hidden rounded-full bg-[var(--surface-alt)]">
        <div
          className="h-full rounded-full bg-[var(--accent-400)]"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-[var(--neutral-600)]">{percentage}%</span>
    </div>
  );
}
