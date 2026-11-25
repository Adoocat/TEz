import { describe, expect, it } from "vitest";

import { joinLines, toPdf, toScreen, type Matrix, type PdfRect } from "./pdfGeometry";

// pdf.js viewport transforms of a 600 × 800 page at scale 1, by rotation.
const PLAIN: Matrix = [1, 0, 0, -1, 0, 800];
const MATRICES: [number, Matrix][] = [
  [0, PLAIN],
  [90, [0, 1, 1, 0, 0, 0]],
  [180, [-1, 0, 0, 1, 600, 0]],
  [270, [0, -1, -1, 0, 800, 600]],
];

describe("page geometry", () => {
  it("puts the top of a page at the top of the screen", () => {
    expect(toScreen(PLAIN, 2, [100, 700, 200, 720])).toEqual({
      left: 200,
      top: 160,
      width: 200,
      height: 40,
    });
  });

  it.each(MATRICES)("comes back from a page turned by %i degrees", (_, matrix) => {
    const rect: PdfRect = [100, 700, 250, 720];

    expect(toPdf(matrix, 1.5, toScreen(matrix, 1.5, rect))).toEqual(rect);
  });

  it("joins the boxes of a line, and keeps lines and columns apart", () => {
    const box = (left: number, top: number, width: number) => ({ left, top, width, height: 10 });

    expect(
      joinLines([
        box(0, 0, 50),
        box(50, 1, 30),
        box(0, 0, 50),
        box(0, 14, 40),
        box(300, 0, 20),
        box(5, 5, 0),
      ]),
    ).toEqual([
      { left: 0, top: 0, width: 80, height: 11 },
      { left: 0, top: 14, width: 40, height: 10 },
      { left: 300, top: 0, width: 20, height: 10 },
    ]);
  });
});
