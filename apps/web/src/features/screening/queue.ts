// The queue's client-side logic: which records a filter shows and which comes next. The
// backend's order is kept as is; moving through it never reorders anything.
import type { components } from "@/api/schema";

export type QueueItem = components["schemas"]["QueueItem"];
export type QueueFilter = components["schemas"]["QueueFilter"];
export type RecordState = components["schemas"]["RecordState"];
export type StateCounts = components["schemas"]["StateCounts"];

export function matches(item: QueueItem, filter: QueueFilter): boolean {
  return filter === "all" || item.state === filter;
}

/**
 * The record after (or before) `from` that the filter shows, wrapping around the queue; the
 * first (or last) one when `from` is not in it. Undefined when no other record matches.
 */
export function step(
  items: readonly QueueItem[],
  from: string | null,
  direction: 1 | -1,
  filter: QueueFilter,
): QueueItem | undefined {
  const ordered = direction === 1 ? items : [...items].reverse();
  const start = from === null ? -1 : ordered.findIndex((item) => item.paper_id === from);
  const rotated =
    start === -1 ? ordered : [...ordered.slice(start + 1), ...ordered.slice(0, start)];
  return rotated.find((item) => matches(item, filter));
}

export function counts(items: readonly QueueItem[]): StateCounts {
  const by: Record<RecordState, number> = {
    undecided: 0,
    include: 0,
    exclude: 0,
    maybe: 0,
    not_retrieved: 0,
  };
  for (const item of items) by[item.state] += 1;
  return { total: items.length, ...by };
}

/** The queue after a decision on one record: same order, that record's new state. */
export function withState(
  items: readonly QueueItem[],
  paperId: string,
  change: Pick<QueueItem, "state" | "decision_id" | "criterion_id">,
): QueueItem[] {
  return items.map((item) => (item.paper_id === paperId ? { ...item, ...change } : item));
}
