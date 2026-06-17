import { cn } from "@/lib/utils/cn";

export function ConfidenceMeter({ value, className }: { value: number; className?: string }) {
  const percentage = Math.round(value * 100);
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="h-2.5 w-32 overflow-hidden rounded-full bg-[var(--surface-alt)]">
        <div
          className="h-full rounded-full bg-[var(--accent-500)]"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs font-semibold text-[var(--neutral-700)]">{percentage}%</span>
    </div>
  );
}
