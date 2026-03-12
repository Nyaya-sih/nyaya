import { cn } from "@/lib/utils/cn";
import { verdictColor } from "@/lib/utils/verdict-color";

export function VerdictBadge({
  verdict,
  className,
}: {
  verdict?: string | null;
  className?: string;
}) {
  const color = verdictColor(verdict);
  const label = verdict && verdict.trim().length ? verdict : "Unknown";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
        className
      )}
      style={{ backgroundColor: `${color}20`, color }}
    >
      {label}
    </span>
  );
}
