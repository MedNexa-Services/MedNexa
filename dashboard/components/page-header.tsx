import * as React from "react";

export function PageHeader({
  title,
  description,
  actions,
  back,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  back?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {back && <div className="mb-2 text-sm">{back}</div>}
        <h1 className="text-[22px] leading-tight font-semibold tracking-[-0.01em] text-foreground">
          {title}
        </h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function StatStrip({
  items,
}: {
  items: { label: string; value: React.ReactNode; hint?: React.ReactNode }[];
}) {
  return (
    <dl className="mb-6 grid grid-cols-2 overflow-hidden rounded-lg border border-border bg-card sm:grid-cols-[repeat(auto-fit,minmax(0,1fr))] sm:divide-x sm:divide-border">
      {items.map((item) => (
        <div key={item.label} className="px-4 py-3">
          <dt className="text-[13px] text-muted-foreground">{item.label}</dt>
          <dd className="tabular mt-0.5 flex items-baseline gap-2">
            <span className="text-xl font-semibold text-foreground">{item.value}</span>
            {item.hint && <span className="text-[13px] text-muted-foreground">{item.hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}
