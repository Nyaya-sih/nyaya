import { cn } from "@/lib/utils/cn";
import { formatCourtName } from "@/lib/utils/court-utils";

export function CourtBadge({ court, className }: { court: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--neutral-600)]",
        className
      )}
    >
      {formatCourtName(court)}
    </span>
  );
}
