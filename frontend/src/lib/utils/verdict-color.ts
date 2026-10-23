export function verdictColor(verdict?: string | null): string {
  if (!verdict) return "var(--neutral-500)";
  const normalized = verdict.toLowerCase();
  if (normalized.includes("convict")) return "var(--verdict-convicted)";
  if (normalized.includes("acquit")) return "var(--verdict-acquitted)";
  if (normalized.includes("dismiss")) return "var(--verdict-dismissed)";
  if (normalized.includes("allow")) return "var(--verdict-allowed)";
  if (normalized.includes("remand")) return "var(--verdict-remanded)";
  if (normalized.includes("settle")) return "var(--verdict-settlement)";
  return "var(--neutral-500)";
}
