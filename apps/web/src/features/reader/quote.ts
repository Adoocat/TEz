// A passage taken out of a document: into a note, with its source chip, or to the clipboard.
import type { TFunction } from "i18next";

import { writeLink } from "@/features/notes/links";

import type { AnchorView } from "./api";
import { citationOf } from "./citation";

/** "Kim et al. 2024, p. 7" */
export function sourceOf(anchor: AnchorView, t: TFunction): string {
  return `${citationOf(anchor.paper, t)}, ${t("reader.pageShort", { page: anchor.page })}`;
}

/** Markdown for a note: the words as a block quote, then the chip that leads back to them. */
export function quoteBlock(anchor: AnchorView, t: TFunction): string {
  const chip = writeLink(sourceOf(anchor, t), "anchor", anchor.id);
  if (anchor.quote === "") return chip;
  // Words that mean something in Markdown are just words here.
  const words = anchor.quote.replace(/([\\`*_[\]<>#])/g, "\\$1");
  return `> ${words}\n>\n> ${chip}`;
}

/** Plain text for anywhere else: the words and where they are from. */
export function quoteWithSource(anchor: AnchorView, t: TFunction): string {
  return `“${anchor.quote}” (${sourceOf(anchor, t)})`;
}
