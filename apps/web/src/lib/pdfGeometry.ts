// Between PDF user space (points, y up, unrotated: what anchors store) and a drawn page (CSS
// pixels, y down, rotated and zoomed). `transform` is the page's own matrix at scale 1
// (pdf.js's viewport.transform).

export type Matrix = readonly [number, number, number, number, number, number];
/** [left, bottom, right, top] in PDF user space. */
export type PdfRect = [number, number, number, number];

export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function toScreen(transform: Matrix, scale: number, rect: PdfRect): ScreenRect {
  const [a, b, c, d, e, f] = transform;
  const point = (x: number, y: number) =>
    [(a * x + c * y + e) * scale, (b * x + d * y + f) * scale] as const;
  const [x0, y0] = point(rect[0], rect[1]);
  const [x1, y1] = point(rect[2], rect[3]);
  return {
    left: Math.min(x0, x1),
    top: Math.min(y0, y1),
    width: Math.abs(x1 - x0),
    height: Math.abs(y1 - y0),
  };
}

export function toPdf(transform: Matrix, scale: number, rect: ScreenRect): PdfRect {
  const [a, b, c, d, e, f] = transform;
  const det = a * d - b * c;
  const point = (left: number, top: number) => {
    const x = left / scale - e;
    const y = top / scale - f;
    return [(d * x - c * y) / det, (a * y - b * x) / det] as const;
  };
  const [x0, y0] = point(rect.left, rect.top);
  const [x1, y1] = point(rect.left + rect.width, rect.top + rect.height);
  const round = (value: number) => Math.round(value * 100) / 100;
  return [
    round(Math.min(x0, x1)),
    round(Math.min(y0, y1)),
    round(Math.max(x0, x1)),
    round(Math.max(y0, y1)),
  ];
}

/** Boxes of one line of text joined: a selection has one per run, some of them twice. */
export function joinLines(rects: readonly ScreenRect[]): ScreenRect[] {
  const lines: ScreenRect[] = [];
  for (const rect of rects) {
    if (rect.width < 0.5 || rect.height < 0.5) continue;
    const line = lines.find((other) => onOneLine(other, rect));
    if (!line) {
      lines.push({ ...rect });
      continue;
    }
    const right = Math.max(line.left + line.width, rect.left + rect.width);
    const bottom = Math.max(line.top + line.height, rect.top + rect.height);
    line.left = Math.min(line.left, rect.left);
    line.top = Math.min(line.top, rect.top);
    line.width = right - line.left;
    line.height = bottom - line.top;
  }
  return lines;
}

function onOneLine(a: ScreenRect, b: ScreenRect): boolean {
  const shared = Math.min(a.top + a.height, b.top + b.height) - Math.max(a.top, b.top);
  if (shared < 0.6 * Math.min(a.height, b.height)) return false;
  // Two columns have lines at the same height; a gap that wide is not a space.
  const gap = Math.max(b.left - (a.left + a.width), a.left - (b.left + b.width));
  return gap < 2 * Math.max(a.height, b.height);
}
