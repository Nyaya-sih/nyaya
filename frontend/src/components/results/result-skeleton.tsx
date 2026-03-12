export function ResultSkeleton() {
  return (
    <div className="surface-card rounded-2xl p-6">
      <div className="flex animate-pulse flex-col gap-4 md:flex-row">
        <div className="h-20 w-20 rounded-full bg-[var(--surface-alt)]" />
        <div className="flex-1 space-y-3">
          <div className="h-5 w-2/3 rounded bg-[var(--surface-alt)]" />
          <div className="h-4 w-full rounded bg-[var(--surface-alt)]" />
          <div className="h-4 w-5/6 rounded bg-[var(--surface-alt)]" />
          <div className="h-2 w-full rounded bg-[var(--surface-alt)]" />
        </div>
      </div>
    </div>
  );
}
