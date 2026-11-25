// The state of the reader's search: the query, the current match, and the marks on the pages
// that are drawn right now.
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";

import { useFind } from "./api";
import { clearFind, drawFind, findRanges } from "./findHighlights";

interface Match {
  page: number;
  /** Which match on its page, from 0. */
  index: number;
}

export function useFindInDocument({
  attachmentId,
  initialQuery,
  initialPage,
  goToPage,
}: {
  attachmentId: string;
  /** A query to start with: full-text search results open the reader this way. */
  initialQuery: string;
  initialPage: number;
  goToPage: (page: number) => void;
}) {
  const [open, setOpen] = useState(initialQuery !== "");
  const [query, setQuery] = useState(initialQuery);
  const deferred = useDeferredValue(open ? query : "");
  const find = useFind(attachmentId, deferred);
  const [position, setPosition] = useState(0);
  const layers = useRef(new Map<number, HTMLElement>());
  const ranges = useRef(new Map<number, Range[]>());
  // The current match is brought into view once its page is drawn.
  const toShow = useRef<Match | null>(null);

  const results = deferred.trim() === "" ? undefined : find.data;
  const matches = useMemo(
    () =>
      (results?.pages ?? []).flatMap(({ page, matches: count }) =>
        Array.from({ length: count }, (_, index): Match => ({ page, index })),
      ),
    [results],
  );
  const current = matches[position];

  const draw = useCallback(() => {
    const range = current ? ranges.current.get(current.page)?.[current.index] : undefined;
    drawFind(ranges.current.values(), range ?? null);
    if (current && range && toShow.current === current) {
      toShow.current = null;
      range.startContainer.parentElement?.scrollIntoView({ block: "center", inline: "nearest" });
    }
  }, [current]);

  // Pages come and go while scrolling; each brings or takes its own matches.
  const onText = useCallback(
    (page: number, layer: HTMLElement | null) => {
      if (layer) {
        layers.current.set(page, layer);
        ranges.current.set(page, findRanges(layer, deferred));
      } else {
        layers.current.delete(page);
        ranges.current.delete(page);
      }
      draw();
    },
    [deferred, draw],
  );

  // A new query: search the drawn pages again.
  useEffect(() => {
    for (const [page, layer] of layers.current)
      ranges.current.set(page, findRanges(layer, deferred));
    draw();
  }, [deferred, draw]);

  // New results: start from the first match at or after the page being read.
  const startFrom = useRef(initialPage);
  const shownFor = useRef<typeof matches | null>(null);
  useEffect(() => {
    if (shownFor.current === matches || matches.length === 0) return;
    shownFor.current = matches;
    const first = matches.findIndex((match) => match.page >= startFrom.current);
    const index = Math.max(first, 0);
    setPosition(index);
    const match = matches[index];
    if (!match) return;
    toShow.current = match;
    goToPage(match.page);
  }, [matches, goToPage]);

  useEffect(() => {
    draw();
  }, [draw, position]);

  useEffect(() => clearFind, []);

  return {
    open,
    query,
    results,
    position: matches.length === 0 ? 0 : position + 1,
    onText,
    show: (fromPage: number) => {
      startFrom.current = fromPage;
      setOpen(true);
    },
    setQuery: (next: string, fromPage: number) => {
      startFrom.current = fromPage;
      setQuery(next);
    },
    close: () => {
      setOpen(false);
      clearFind();
    },
    step: (direction: 1 | -1) => {
      if (matches.length === 0) return;
      const index = (position + direction + matches.length) % matches.length;
      const match = matches[index];
      if (!match) return;
      setPosition(index);
      toShow.current = match;
      if (!layers.current.has(match.page)) goToPage(match.page);
    },
  };
}
