import { cn } from "@/lib/utils/cn";

export function ShimmerCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("shimmer-border surface-card rounded-2xl p-8", className)}>
      {children}
    </div>
  );
}
