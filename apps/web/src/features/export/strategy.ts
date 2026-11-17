// The search strategy table for a thesis' methods chapter (Task 40): one row per search run,
// as Markdown (paste into a chapter) and CSV (open in a spreadsheet). Pure, so it is tested
// without a screen; the labels come from i18n.
import type { StrategyRow } from "./api";

export interface StrategyLabels {
  headers: [string, string, string, string, string, string, string];
  source: (row: StrategyRow) => string;
  method: (row: StrategyRow) => string;
  /** What a run that failed or stopped early adds to its row. */
  status: (row: StrategyRow) => string;
  /** The cell of an empty value (no query, no reported count). */
  none: string;
}

/** The run's date in the user's time zone, as YYYY-MM-DD (unambiguous in any language). */
export function localDate(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function cells(rows: StrategyRow[], labels: StrategyLabels): string[][] {
  return rows.map((row, index) => {
    const status = labels.status(row);
    return [
      String(index + 1),
      labels.source(row),
      labels.method(row),
      localDate(row.executed_at),
      row.query ?? labels.none,
      row.total_reported === null ? labels.none : String(row.total_reported),
      status ? `${String(row.retrieved)} (${status})` : String(row.retrieved),
    ];
  });
}

function markdownCell(value: string): string {
  return value.replace(/\s+/g, " ").replace(/\\/g, "\\\\").replace(/\|/g, "\\|").trim();
}

export function strategyMarkdown(rows: StrategyRow[], labels: StrategyLabels): string {
  const line = (values: string[]) => `| ${values.map(markdownCell).join(" | ")} |`;
  return [
    line(labels.headers),
    line(labels.headers.map((_, index) => (index === 0 || index >= 5 ? "--:" : "---"))),
    ...cells(rows, labels).map(line),
  ].join("\n");
}

function csvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** RFC 4180, CRLF line ends. */
export function strategyCsv(rows: StrategyRow[], labels: StrategyLabels): string {
  return [labels.headers, ...cells(rows, labels)]
    .map((values) => values.map(csvCell).join(","))
    .join("\r\n");
}
