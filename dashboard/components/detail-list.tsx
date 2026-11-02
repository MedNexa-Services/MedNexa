import * as React from "react";
import Link from "next/link";

export function DetailList({ items }: { items: { label: string; value: React.ReactNode }[] }) {
  return (
    <dl className="divide-y divide-border">
      {items
        .filter((item) => item.value !== null && item.value !== undefined && item.value !== "" && item.value !== false)
        .map((item) => (
          <div key={item.label} className="grid gap-1 px-4 py-2.5 sm:grid-cols-[8rem_1fr] sm:gap-4">
            <dt className="text-[13px] text-muted-foreground">{item.label}</dt>
            <dd className="text-sm text-foreground">{item.value}</dd>
          </div>
        ))}
    </dl>
  );
}

export function BackLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-muted-foreground hover:text-foreground">
      <span aria-hidden>‹ </span>
      {children}
    </Link>
  );
}
