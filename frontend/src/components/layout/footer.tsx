import { Container } from "@/components/layout/container";

export function Footer() {
  return (
    <footer className="relative z-10 mt-24 border-t border-[var(--border)] bg-[var(--surface)]/85 backdrop-blur">
      <Container className="flex flex-col gap-6 py-10 text-sm text-[var(--neutral-600)] md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[var(--neutral-700)]">
            NyayaAI is a decision-support tool for legal research.
          </p>
          <p className="mt-1 text-xs">
            Always verify with primary sources. Not legal advice.
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs uppercase tracking-[0.08em]">
          <span>Privacy</span>
          <span>Terms</span>
          <span>Security</span>
          <span>© 2026 NyayaAI</span>
        </div>
      </Container>
    </footer>
  );
}
