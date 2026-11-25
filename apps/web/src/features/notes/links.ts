// The links of a note's Markdown (ADR 0034): `[words](tez:note/<id>)`, `tez:paper/…`,
// `tez:anchor/…`, and `[[name]]` typed by hand.
import type { NoteLinkView } from "./api";

export type LinkType = "note" | "paper" | "anchor";

export interface WrittenLink {
  from: number;
  to: number;
  label: string;
  /** Null for `[[name]]`: what it names is known from the saved note. */
  type: LinkType | null;
  id: string | null;
}

const LINK =
  /\[([^[\]\n]*)\]\(tez:(note|paper|anchor)\/([0-9A-Za-z-]{1,36})\)|\[\[([^[\]\n]+)\]\]/g;

export function linksIn(text: string): WrittenLink[] {
  return [...text.matchAll(LINK)].map((found) => {
    const [whole, label, type, id, name] = found;
    return {
      from: found.index,
      to: found.index + whole.length,
      label: name ?? label ?? "",
      type: name === undefined ? (type as LinkType) : null,
      id: name === undefined ? (id ?? null) : null,
    };
  });
}

/** A link as the editor writes it. Brackets would end the words too early. */
export function writeLink(label: string, type: LinkType, id: string): string {
  const words = label.replace(/\[/g, "(").replace(/\]/g, ")").replace(/\s+/g, " ").trim();
  return `[${words}](tez:${type}/${id})`;
}

/** What the saved note knows about a link. Undefined while it is not saved yet. */
export function statusOf(
  link: Pick<WrittenLink, "type" | "id" | "label">,
  known: readonly NoteLinkView[],
): NoteLinkView | undefined {
  return known.find((view) =>
    link.id === null ? view.label === link.label.trim() : view.target_id === link.id,
  );
}

/** `[[name]]` as a Markdown link, for the preview: `tez:name/<name>`. */
export function nameLinks(text: string): string {
  return text.replace(
    /\[\[([^[\]\n]+)\]\]/g,
    (_, name: string) => `[${name.trim()}](tez:name/${encodeURIComponent(name.trim())})`,
  );
}
