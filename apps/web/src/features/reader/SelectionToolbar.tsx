// The small box above selected text (design 4.5): highlight colours and what else can be done
// with the passage.
import { MessageSquarePlus } from "lucide-react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { ShortcutKeys } from "@/lib/shortcuts/ShortcutKeys";

import { highlightColors, highlightVar, type HighlightColor } from "./api";

export function SelectionToolbar({
  at,
  color,
  onHighlight,
  onComment,
  children,
}: {
  /** The top middle of the selection, in the window. */
  at: { x: number; y: number };
  /** The colour `H` uses. */
  color: HighlightColor;
  onHighlight: (color: HighlightColor) => void;
  onComment: () => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const above = at.y > 64;
  return createPortal(
    <div
      role="toolbar"
      aria-label={t("reader.selection.label")}
      className="fixed z-[var(--z-popover)] flex -translate-x-1/2 items-center gap-1 rounded-md border border-line bg-raised p-1 shadow-popover"
      style={{ left: Math.max(160, at.x), top: above ? at.y - 48 : at.y + 32 }}
      // A press must not move the selection it acts on.
      onMouseDown={(event) => {
        event.preventDefault();
      }}
    >
      {highlightColors.map((name) => (
        <button
          key={name}
          type="button"
          aria-label={t(`reader.selection.highlight.${name}`)}
          className="grid size-7 place-items-center rounded-full hover:bg-hovered"
          onClick={() => {
            onHighlight(name);
          }}
        >
          <span
            aria-hidden
            className="size-4 rounded-full ring-offset-2 data-[last=true]:ring-2 data-[last=true]:ring-fg"
            data-last={name === color}
            style={{ backgroundColor: highlightVar(name) }}
          />
        </button>
      ))}
      <ShortcutKeys context="reader" id="highlight" className="mr-1" />
      <Button size="sm" variant="ghost" onClick={onComment}>
        <MessageSquarePlus aria-hidden />
        {t("reader.selection.comment")}
      </Button>
      {children}
    </div>,
    document.body,
  );
}
