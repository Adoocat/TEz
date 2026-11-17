// The export screen's pure parts: the strategy table as Markdown and CSV, the `tez export`
// command, and the bibliography HTML turned into safe elements.
import { render } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";

import type { StrategyRow } from "./api";
import { exportCommand } from "./command";
import { InlineHtml } from "./InlineHtml";
import { localDate, strategyCsv, strategyMarkdown, type StrategyLabels } from "./strategy";

const row = (overrides: Partial<StrategyRow>): StrategyRow => ({
  run_id: "run",
  source: "openalex",
  method: "database",
  snowball_round: null,
  executed_at: "2026-03-01T09:00:00Z",
  query: null,
  file_name: null,
  total_reported: null,
  retrieved: 0,
  status: "ok",
  ...overrides,
});

const labels: StrategyLabels = {
  headers: ["#", "Source", "Method", "Date", "Query", "Reported", "Retrieved"],
  source: (r) => r.source,
  method: (r) => r.method,
  status: (r) => (r.status === "ok" ? "" : r.status),
  none: "—",
};

describe("the search strategy table", () => {
  const rows = [
    row({ query: 'a | b\nAND "c"', total_reported: 12, retrieved: 10 }),
    row({ source: "Scopus", query: "x, y", retrieved: 3, status: "error" }),
  ];

  it("is a Markdown table with one row per run and escaped cells", () => {
    expect(strategyMarkdown(rows, labels).split("\n")).toEqual([
      "| # | Source | Method | Date | Query | Reported | Retrieved |",
      "| --: | --- | --- | --- | --- | --: | --: |",
      `| 1 | openalex | database | ${localDate(rows[0]?.executed_at ?? "")} | a \\| b AND "c" | 12 | 10 |`,
      `| 2 | Scopus | database | ${localDate(rows[1]?.executed_at ?? "")} | x, y | — | 3 (error) |`,
    ]);
  });

  it("is RFC 4180 CSV", () => {
    const date = localDate(rows[0]?.executed_at ?? "");
    expect(strategyCsv(rows, labels).split("\r\n")).toEqual([
      "#,Source,Method,Date,Query,Reported,Retrieved",
      `1,openalex,database,${date},"a | b\nAND ""c""",12,10`,
      `2,Scopus,database,${date},"x, y",—,3 (error)`,
    ]);
  });

  it("dates runs as YYYY-MM-DD", () => {
    expect(localDate("2026-03-01T12:00:00Z")).toMatch(/^2026-03-0[12]$/);
  });
});

describe("the terminal command", () => {
  it("names the review, collection or nothing, quoting where needed", () => {
    expect(
      exportCommand("bibtex", { kind: "review", title: "Öğretmen SLR", included: true }, "a.bib"),
    ).toBe('tez export --format bibtex --review "Öğretmen SLR" --included --output a.bib');
    expect(exportCommand("ris", { kind: "collection", name: "Tez" }, "refs.ris")).toBe(
      "tez export --format ris --collection Tez --output refs.ris",
    );
    expect(exportCommand("bibtex", { kind: "library" }, "references.bib")).toBe(
      "tez export --format bibtex --output references.bib",
    );
    expect(
      exportCommand("bibtex", { kind: "review", title: 'say "hi"', included: false }, "x.bib"),
    ).toBe('tez export --format bibtex --review "say \\"hi\\"" --output x.bib');
  });
});

describe("bibliography HTML", () => {
  it("keeps the style's formatting and nothing else", () => {
    const { container } = render(
      createElement(InlineHtml, {
        html: 'A &amp; B. <i>T</i><sup>2</sup> <span style="font-variant:small-caps;">sc</span> <script>x()</script><a href="http://x">link</a> <img src=x onerror="alert(1)">',
      }),
    );

    expect(container.innerHTML).toBe(
      'A &amp; B. <i>T</i><sup>2</sup> <span class="[font-variant:small-caps]">sc</span> x()link ',
    );
  });
});
