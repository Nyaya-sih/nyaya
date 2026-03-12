"use client";

import { useCallback } from "react";
import { cn } from "@/lib/utils/cn";

export function SpotlightCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const handleMove = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    event.currentTarget.style.setProperty("--spotlight-x", `${x}%`);
    event.currentTarget.style.setProperty("--spotlight-y", `${y}%`);
  }, []);

  return (
    <div
      onMouseMove={handleMove}
      className={cn("spotlight-card surface-card rounded-xl p-6 transition", className)}
    >
      {children}
    </div>
  );
}
