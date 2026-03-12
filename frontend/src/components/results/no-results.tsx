export function NoResults() {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-10 text-center">
      <h3 className="text-lg font-semibold text-[var(--primary-900)]">
        No similar cases found
      </h3>
      <p className="mt-2 text-sm text-[var(--neutral-600)]">
        Try broadening filters or switching to Combined similarity mode.
      </p>
    </div>
  );
}
