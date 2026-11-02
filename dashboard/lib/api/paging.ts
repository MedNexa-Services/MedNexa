import type { Page } from "./types";

export const MAX_PAGE_SIZE = 200;

export async function fetchAllPages<T>(
  fetchPage: (limit: number, offset: number) => Promise<Page<T>>,
  maxItems = 2000
): Promise<{ items: T[]; total: number; truncated: boolean }> {
  const items: T[] = [];
  let total = 0;
  while (items.length < maxItems) {
    const page = await fetchPage(MAX_PAGE_SIZE, items.length);
    total = page.total;
    items.push(...page.items);
    if (page.items.length === 0 || items.length >= total) break;
  }
  return { items, total, truncated: items.length < total };
}
