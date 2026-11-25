// `?anchor=<id>`: open the reader at a place in the document (a source chip, a highlight in a
// list, matrix evidence) and show it for a moment (design 4.5 "Konuma atlama").
import { useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router";

import { useAnchor, type AnchorView } from "./api";

const FLASH_MS = 2000;

export interface AnchorTarget {
  /** The place to show now, for as long as it is shown. */
  flash: AnchorView | null;
  /** A place that cannot be shown: gone from the file, or not looked up yet. */
  missing: AnchorView | null;
  dismiss: () => void;
}

export function useAnchorTarget({
  enabled,
  ready,
  goTo,
}: {
  enabled: boolean;
  /** The pages have their size, so a jump lands where it should. */
  ready: boolean;
  goTo: (anchor: AnchorView) => void;
}): AnchorTarget {
  const [params] = useSearchParams();
  const { key } = useLocation();
  const asked = enabled ? params.get("anchor") : null;
  // The address drops the anchor once the page is turned; what was asked for stays.
  const [target, setTarget] = useState<{ id: string; key: string } | null>(null);
  if (asked && target?.key !== key) setTarget({ id: asked, key });
  // The jump whose moment is over (or that was dismissed).
  const [over, setOver] = useState<string | null>(null);
  const jumped = useRef<string | null>(null);

  const anchor = useAnchor(target?.id ?? null).data;
  const usable = anchor?.status === "verified" || anchor?.status === "unverified";
  const current = anchor && target && over !== target.key ? anchor : null;
  const jump = current && usable && ready ? target?.key : undefined;

  useEffect(() => {
    if (jump === undefined || !anchor || jumped.current === jump) return;
    jumped.current = jump;
    goTo(anchor);
  }, [jump, anchor, goTo]);
  useEffect(() => {
    if (jump === undefined) return;
    const timer = setTimeout(() => {
      setOver(jump);
    }, FLASH_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [jump]);

  return {
    flash: jump === undefined ? null : current,
    missing: current && !usable ? current : null,
    dismiss: () => {
      if (target) setOver(target.key);
    },
  };
}
