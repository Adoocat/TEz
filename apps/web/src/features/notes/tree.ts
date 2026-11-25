// The note tree, from the flat list's `parent_id`.
import type { NoteSummary } from "./api";

export interface TreeNote {
  note: NoteSummary;
  depth: number;
}

/** Depth first, siblings by title. A note whose parent is missing stands at the top. */
export function treeOf(notes: readonly NoteSummary[], language: string): TreeNote[] {
  const known = new Set(notes.map((note) => note.id));
  const children = new Map<string | null, NoteSummary[]>();
  for (const note of notes) {
    const parent = note.parent_id !== null && known.has(note.parent_id) ? note.parent_id : null;
    children.set(parent, [...(children.get(parent) ?? []), note]);
  }
  const collator = new Intl.Collator(language, { numeric: true });
  const walk = (parent: string | null, depth: number): TreeNote[] =>
    (children.get(parent) ?? [])
      .toSorted((a, b) => collator.compare(a.title, b.title))
      .flatMap((note) => [{ note, depth }, ...walk(note.id, depth + 1)]);
  return walk(null, 0);
}

/** Notes a note can be moved into: not itself, not what is inside it. */
export function possibleParents(notes: readonly NoteSummary[], id: string): NoteSummary[] {
  const inside = new Set([id]);
  for (let grown = true; grown;) {
    grown = false;
    for (const note of notes) {
      if (note.parent_id !== null && inside.has(note.parent_id) && !inside.has(note.id)) {
        inside.add(note.id);
        grown = true;
      }
    }
  }
  return notes.filter((note) => !inside.has(note.id));
}
