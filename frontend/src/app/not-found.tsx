import Link from "next/link";
import { Container } from "@/components/layout/container";

export default function NotFound() {
  return (
    <Container className="py-20 text-center">
      <h2 className="text-3xl font-semibold text-[var(--primary-900)]">Page not found</h2>
      <p className="mt-2 text-sm text-[var(--neutral-600)]">
        The resource you requested does not exist.
      </p>
      <Link
        href="/"
        className="mt-6 inline-flex rounded-full bg-[var(--primary-700)] px-4 py-2 text-xs font-semibold text-white"
      >
        Back to home
      </Link>
    </Container>
  );
}
