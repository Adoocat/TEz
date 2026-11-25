// Turkish-safe matching, the frontend twin of backend `tez.shared.text.fold`: every i-like
// letter (I, İ, ı, i) becomes "i", case and diacritics are dropped. Both sides are checked
// against backend/tests/fixtures/text/fold_cases.json.

const I_VARIANTS = /[Iİı]/g;
const COMBINING = /\p{M}/gu;
// What Python's casefold does beyond lower-casing, for the letters we are likely to meet.
const CASEFOLD: Record<string, string> = { ß: "ss", ẞ: "ss", ς: "σ" };

export function fold(text: string): string {
  return text
    .normalize("NFKC")
    .replace(I_VARIANTS, "i")
    .toLowerCase()
    .replace(/[ßẞς]/g, (ch) => CASEFOLD[ch] ?? ch)
    .normalize("NFKD")
    .replace(COMBINING, "");
}

/** `fold(text)` with, for each folded character, the index in `text` it came from. */
export function foldWithMap(text: string): { folded: string; origin: number[] } {
  let folded = "";
  const origin: number[] = [];
  let index = 0;
  for (const ch of text) {
    const piece = fold(ch);
    origin.push(...Array.from({ length: piece.length }, () => index));
    folded += piece;
    index += ch.length;
  }
  return { folded, origin };
}

export interface Segment<T> {
  text: string;
  /** The term this piece matched, or undefined for plain text. */
  match?: T;
}

const WORD = /[\p{L}\p{N}]/u;

/**
 * Split `text` into plain pieces and pieces matching a term. A term matches from the start
 * of a word ("review" in "reviews", not in "preview"); longer terms win where two overlap.
 */
export function highlight<T>(
  text: string,
  terms: readonly { term: string; value: T }[],
): Segment<T>[] {
  const { folded, origin } = foldWithMap(text);
  origin.push(text.length);

  const wanted = terms
    .map(({ term, value }) => ({ needle: fold(term).trim(), value }))
    .filter(({ needle }) => needle.length > 0)
    .sort((a, b) => b.needle.length - a.needle.length);
  const taken: { start: number; end: number; value: T }[] = [];
  for (const { needle, value } of wanted) {
    let from = folded.indexOf(needle);
    while (from !== -1) {
      const to = from + needle.length;
      const atWordStart = from === 0 || !WORD.test(folded[from - 1] ?? "");
      const start = origin[from] ?? 0;
      const end = origin[to] ?? text.length;
      if (atWordStart && !taken.some((t) => start < t.end && end > t.start)) {
        taken.push({ start, end, value });
      }
      from = folded.indexOf(needle, from + 1);
    }
  }
  taken.sort((a, b) => a.start - b.start);

  const segments: Segment<T>[] = [];
  let at = 0;
  for (const { start, end, value } of taken) {
    if (start > at) segments.push({ text: text.slice(at, start) });
    segments.push({ text: text.slice(start, end), match: value });
    at = end;
  }
  if (at < text.length) segments.push({ text: text.slice(at) });
  return segments;
}
