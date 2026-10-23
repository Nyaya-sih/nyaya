const COURT_MAP: Record<string, string> = {
  "DL_HC": "Delhi High Court",
  "BH_HC": "Bombay High Court",
  "PH_HC": "Patna High Court",
};

export function formatCourtName(codeOrName: string): string {
  return COURT_MAP[codeOrName] ?? codeOrName;
}
