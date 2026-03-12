"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";

export function LegalDisclaimer({ text }: { text?: string }) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--neutral-700)] shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />
          <span>{text ?? "This is an AI-powered research tool, not legal advice."}</span>
        </div>
        <button
          type="button"
          onClick={() => setVisible(false)}
          className="text-xs text-[var(--neutral-500)]"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
