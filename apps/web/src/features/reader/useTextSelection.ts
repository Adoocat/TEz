import { useEffect, useState, type RefObject } from "react";

import { selectionInLayer } from "./selection";

export interface TextSelection {
  layer: HTMLElement;
  range: Range;
  page: number;
  /** The top middle of the selection, in the window. */
  at: { x: number; y: number };
}

/** The text selected in the document, once the pointer has let go of it. */
export function useTextSelection(root: RefObject<HTMLElement | null>) {
  const [selection, setSelection] = useState<TextSelection | null>(null);
  useEffect(() => {
    let pressed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = () => {
      const found = root.current ? selectionInLayer(getSelection(), root.current) : null;
      if (!found) {
        setSelection(null);
        return;
      }
      const box = found.range.getBoundingClientRect();
      setSelection({ ...found, at: { x: box.left + box.width / 2, y: box.top } });
    };
    const later = () => {
      clearTimeout(timer);
      timer = setTimeout(read, 60);
    };
    const onDown = (event: PointerEvent) => {
      // The toolbar is outside the document; pressing it keeps the selection.
      pressed = root.current?.contains(event.target as Node) ?? false;
    };
    const onUp = () => {
      if (!pressed) return;
      pressed = false;
      later();
    };
    const onChange = () => {
      // Not while it is still being dragged.
      if (!pressed) later();
    };
    // The box is placed in the window: scrolling the document moves the text under it.
    const scroller = root.current;
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("pointerup", onUp);
    document.addEventListener("selectionchange", onChange);
    scroller?.addEventListener("scroll", onChange);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("selectionchange", onChange);
      scroller?.removeEventListener("scroll", onChange);
    };
  }, [root]);
  return {
    selection,
    clear: () => {
      getSelection()?.removeAllRanges();
      setSelection(null);
    },
  };
}
