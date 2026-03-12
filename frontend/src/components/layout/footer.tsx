import { Container } from "@/components/layout/container";

export function Footer() {
  return (
    <footer className="mt-20 border-t border-[var(--border)] bg-[var(--surface)]">
      <Container className="flex flex-col gap-6 py-10 text-sm text-[var(--neutral-600)] md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[var(--neutral-700)]">
            NyayaAI is a decision-support tool for legal research.
          </p>
          <p className="text-xs">
            Always verify with primary sources. Not legal advice.
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs">
          <span>Privacy</span>
          <span>Terms</span>
          <span>Security</span>
          <span>© 2026 NyayaAI</span>
        </div>
      </Container>
    </footer>
  );
}
