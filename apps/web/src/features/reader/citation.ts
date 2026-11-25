import type { TFunction } from "i18next";

import type { AnchorView } from "./api";

/** "Kim et al. 2024": a paper as a source chip names it. */
export function citationOf(paper: AnchorView["paper"], t: TFunction): string {
  const family = paper.first_author?.split(" ").at(-1);
  const author = !family
    ? paper.title
    : paper.author_count > 2
      ? t("reader.citation.many", { author: family })
      : family;
  return [author, paper.year].filter(Boolean).join(" ");
}
