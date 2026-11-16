// The PRISMA 2020 flow diagram as a standalone SVG document (Task 35): every number comes
// from GET /reviews/{id}/prisma (Task 34), box titles from the user's saved labels or the
// translated defaults. The same string is shown on screen and exported, so what is saved is
// what was seen; colours are resolved values, so the file opens on its own.
import type { components } from "@/api/schema";

export type PrismaCounts = components["schemas"]["PrismaCounts"];
type Branch =
  components["schemas"]["DatabasesBranch"] | components["schemas"]["OtherMethodsBranch"];

export const boxKeys = [
  "identification",
  "screening",
  "included_phase",
  "db_identified",
  "db_removed",
  "db_screened",
  "db_excluded",
  "db_sought",
  "db_not_retrieved",
  "db_assessed",
  "db_reports_excluded",
  "other_identified",
  "other_removed",
  "other_screened",
  "other_excluded",
  "other_sought",
  "other_not_retrieved",
  "other_assessed",
  "other_reports_excluded",
  "included",
] as const;
export type BoxKey = (typeof boxKeys)[number];

export interface Palette {
  text: string;
  muted: string;
  line: string;
  fill: string;
  page: string;
  /** Accent per branch and for exclusions; all equal to `line` in the print theme. */
  database: string;
  other: string;
  excluded: string;
}

export interface DiagramText {
  /** The box's title: the saved label, else the translated default. */
  title: (key: BoxKey) => string;
  /** "(n = 1,425)" in the reader's language. */
  n: (value: number) => string;
  /** One line inside a box: "Scopus (n = 842)", "Awaiting decision (n = 3)". */
  line: (label: string, value: number) => string;
  source: (name: string) => string;
  method: (method: string, round: number | null) => string;
  reason: (code: string | null, text: string | null) => string;
  awaiting: string;
  duplicates: string;
  notTaken: string;
  documentTitle: string;
}

interface Line {
  text: string;
  strong?: boolean;
}

interface Box {
  key: BoxKey;
  column: number;
  row: number;
  lines: Line[];
  accent: keyof Pick<Palette, "database" | "other" | "excluded" | "line">;
  dashed?: boolean;
}

/** The print theme: ink on paper. An exported document needs literal colours, and a
 * black-and-white printout should not depend on the screen's theme. */
export const printPalette: Palette = {
  text: "#000000",
  muted: "#000000",
  line: "#000000",
  fill: "#ffffff",
  page: "#ffffff",
  database: "#000000",
  other: "#000000",
  excluded: "#000000",
};

const COLUMN_WIDTH = 250;
const GAP = 30;
const LEFT = 56;
const TOP = 56;
const ROW_GAP = 36;
const LINE_HEIGHT = 17;
const PADDING = 10;
const FONT_SIZE = 12;
// An average glyph at 12px in a sans-serif face; enough to break lines before the edge.
const CHAR_WIDTH = 6.4;

export function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/** Break a line into pieces that fit the box, at spaces where possible. */
export function wrap(text: string, width = COLUMN_WIDTH - 2 * PADDING): string[] {
  const max = Math.max(8, Math.floor(width / CHAR_WIDTH));
  const out: string[] = [];
  let current = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    if (word.length > max) {
      if (current) out.push(current);
      for (let i = 0; i < word.length; i += max) out.push(word.slice(i, i + max));
      current = "";
      continue;
    }
    const next = current ? `${current} ${word}` : word;
    if (next.length > max) {
      out.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) out.push(current);
  return out.length > 0 ? out : [""];
}

function branchBoxes(
  branch: Branch,
  prefix: "db" | "other",
  column: number,
  text: DiagramText,
  identifiedLines: Line[],
): Box[] {
  const accent = prefix === "db" ? "database" : "other";
  const k = (name: string) => `${prefix}_${name}` as BoxKey;
  const awaiting = (value: number): Line[] =>
    value > 0 ? [{ text: text.line(text.awaiting, value) }] : [];
  return [
    {
      key: k("identified"),
      column,
      row: 0,
      accent,
      dashed: prefix === "other",
      lines: [
        { text: `${text.title(k("identified"))} ${text.n(branch.identified)}`, strong: true },
        ...identifiedLines,
      ],
    },
    {
      key: k("removed"),
      column: column + 1,
      row: 0,
      accent: "line",
      lines: [
        { text: text.title(k("removed")), strong: true },
        { text: text.line(text.duplicates, branch.duplicates) },
        { text: text.line(text.notTaken, branch.not_taken) },
      ],
    },
    {
      key: k("screened"),
      column,
      row: 1,
      accent,
      dashed: prefix === "other",
      lines: [
        { text: `${text.title(k("screened"))} ${text.n(branch.screened)}`, strong: true },
        ...awaiting(branch.awaiting_screening),
      ],
    },
    {
      key: k("excluded"),
      column: column + 1,
      row: 1,
      accent: "excluded",
      lines: [{ text: `${text.title(k("excluded"))} ${text.n(branch.excluded)}`, strong: true }],
    },
    {
      key: k("sought"),
      column,
      row: 2,
      accent,
      dashed: prefix === "other",
      lines: [{ text: `${text.title(k("sought"))} ${text.n(branch.sought)}`, strong: true }],
    },
    {
      key: k("not_retrieved"),
      column: column + 1,
      row: 2,
      accent: "excluded",
      lines: [
        { text: `${text.title(k("not_retrieved"))} ${text.n(branch.not_retrieved)}`, strong: true },
      ],
    },
    {
      key: k("assessed"),
      column,
      row: 3,
      accent,
      dashed: prefix === "other",
      lines: [
        { text: `${text.title(k("assessed"))} ${text.n(branch.assessed)}`, strong: true },
        ...awaiting(branch.awaiting_full_text),
      ],
    },
    {
      key: k("reports_excluded"),
      column: column + 1,
      row: 3,
      accent: "excluded",
      lines: [
        {
          text: `${text.title(k("reports_excluded"))} ${text.n(
            branch.excluded_reports.reduce((sum, reason) => sum + reason.count, 0),
          )}`,
          strong: true,
        },
        ...branch.excluded_reports.map((reason) => ({
          text: text.line(text.reason(reason.code, reason.text), reason.count),
        })),
      ],
    },
  ];
}

/** The diagram's boxes; the other-methods side only when it found anything. */
export function layout(counts: PrismaCounts, text: DiagramText): Box[] {
  const boxes = branchBoxes(
    counts.databases,
    "db",
    0,
    text,
    counts.databases.sources.map((source) => ({
      text: text.line(text.source(source.source), source.identified),
    })),
  );
  const others = counts.other_methods.identified > 0;
  if (others) {
    boxes.push(
      ...branchBoxes(
        counts.other_methods,
        "other",
        2,
        text,
        counts.other_methods.methods.map((m) => ({
          text: text.line(text.method(m.method, m.round ?? null), m.identified),
        })),
      ),
    );
  }
  boxes.push({
    key: "included",
    column: 0,
    row: 4,
    accent: "database",
    lines: [{ text: `${text.title("included")} ${text.n(counts.included)}`, strong: true }],
  });
  return boxes;
}

interface Placed extends Box {
  x: number;
  y: number;
  width: number;
  height: number;
  wrapped: Line[];
}

function place(boxes: Box[]): { placed: Placed[]; width: number; height: number } {
  const wrapped = boxes.map((box) => ({
    box,
    lines: box.lines.flatMap((line) =>
      wrap(line.text).map((piece): Line => ({ text: piece, strong: line.strong === true })),
    ),
  }));
  const rows = Math.max(...boxes.map((b) => b.row)) + 1;
  const columns = Math.max(...boxes.map((b) => b.column)) + 1;
  const rowHeight = Array.from({ length: rows }, (_, row) =>
    Math.max(
      40,
      ...wrapped
        .filter(({ box }) => box.row === row)
        .map(({ lines }) => 2 * PADDING + lines.length * LINE_HEIGHT),
    ),
  );
  const rowTop = rowHeight.reduce<number[]>(
    (tops, h, i) => [...tops, (tops[i] ?? TOP) + h + ROW_GAP],
    [TOP],
  );
  const placed = wrapped.map(({ box, lines }) => ({
    ...box,
    x: LEFT + box.column * (COLUMN_WIDTH + GAP),
    y: rowTop[box.row] ?? TOP,
    width: COLUMN_WIDTH,
    height: rowHeight[box.row] ?? 40,
    wrapped: lines,
  }));
  return {
    placed,
    width: LEFT + columns * (COLUMN_WIDTH + GAP),
    height: (rowTop[rows] ?? TOP) + 20,
  };
}

function arrow(x1: number, y1: number, x2: number, y2: number, color: string): string {
  return `<line x1="${String(x1)}" y1="${String(y1)}" x2="${String(x2)}" y2="${String(y2)}" stroke="${escapeXml(color)}" stroke-width="1.2" marker-end="url(#arrow)"/>`;
}

/** The whole diagram as an SVG document that opens on its own. */
export function prismaSvg(counts: PrismaCounts, text: DiagramText, palette: Palette): string {
  const { placed, width, height } = place(layout(counts, text));
  const at = (key: BoxKey) => placed.find((b) => b.key === key);
  const parts: string[] = [];
  const font = "Inter, Helvetica, Arial, sans-serif";

  for (const box of placed) {
    const stroke = palette[box.accent];
    parts.push(
      `<g data-box="${box.key}"><rect x="${String(box.x)}" y="${String(box.y)}" width="${String(box.width)}" height="${String(box.height)}" rx="4" fill="${escapeXml(palette.fill)}" stroke="${escapeXml(stroke)}" stroke-width="1.2"${box.dashed ? ' stroke-dasharray="5 3"' : ""}/>`,
    );
    box.wrapped.forEach((line, index) => {
      const y = box.y + PADDING + (index + 1) * LINE_HEIGHT - 4;
      parts.push(
        `<text x="${String(box.x + PADDING)}" y="${String(y)}" font-family="${font}" font-size="${String(FONT_SIZE)}" fill="${escapeXml(line.strong ? palette.text : palette.muted)}"${line.strong ? ' font-weight="600"' : ""}>${escapeXml(line.text)}</text>`,
      );
    });
    parts.push("</g>");
  }

  // Down each main column, and across to its side boxes.
  for (const prefix of ["db", "other"] as const) {
    const chain = ["identified", "screened", "sought", "assessed"].map((n) =>
      at(`${prefix}_${n}` as BoxKey),
    );
    chain.forEach((box, i) => {
      const next = chain[i + 1] ?? (prefix === "db" ? at("included") : undefined);
      if (box && next) {
        parts.push(
          arrow(
            box.x + box.width / 2,
            box.y + box.height,
            next.x + next.width / 2,
            next.y,
            palette.line,
          ),
        );
      }
    });
    const sides = ["removed", "excluded", "not_retrieved", "reports_excluded"];
    chain.forEach((box, i) => {
      const side = at(`${prefix}_${sides[i] ?? ""}` as BoxKey);
      if (box && side) {
        const y = box.y + Math.min(box.height, side.height) / 2;
        parts.push(arrow(box.x + box.width, y, side.x, y, palette.line));
      }
    });
  }
  // The other methods' assessed reports join the included studies.
  const otherAssessed = at("other_assessed");
  const included = at("included");
  if (otherAssessed && included) {
    const x = otherAssessed.x + otherAssessed.width / 2;
    const y = included.y + included.height / 2;
    parts.push(
      `<polyline points="${String(x)},${String(otherAssessed.y + otherAssessed.height)} ${String(x)},${String(y)} ${String(included.x + included.width)},${String(y)}" fill="none" stroke="${escapeXml(palette.line)}" stroke-width="1.2" marker-end="url(#arrow)"/>`,
    );
  }

  // Phase names down the left edge, rotated as in the PRISMA template.
  const phase = (key: BoxKey, from: number, to: number) => {
    const middle = (from + to) / 2;
    return `<text transform="translate(${String(LEFT / 2)} ${String(middle)}) rotate(-90)" text-anchor="middle" font-family="${font}" font-size="${String(FONT_SIZE)}" font-weight="600" fill="${escapeXml(palette.text)}">${escapeXml(text.title(key))}</text>`;
  };
  const top = (key: BoxKey) => at(key)?.y ?? TOP;
  const bottom = (key: BoxKey) => {
    const box = at(key);
    return box ? box.y + box.height : TOP;
  };
  parts.push(phase("identification", top("db_identified"), bottom("db_identified")));
  parts.push(phase("screening", top("db_screened"), bottom("db_assessed")));
  parts.push(phase("included_phase", top("included"), bottom("included")));

  return [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${String(width)}" height="${String(height)}" viewBox="0 0 ${String(width)} ${String(height)}" role="img" aria-labelledby="prisma-title">`,
    `<title id="prisma-title">${escapeXml(text.documentTitle)}</title>`,
    `<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="${escapeXml(palette.line)}"/></marker></defs>`,
    `<rect width="100%" height="100%" fill="${escapeXml(palette.page)}"/>`,
    ...parts,
    `</svg>`,
  ].join("\n");
}
