// How a matrix cell is shown and how what the user types is read (Task 52). The backend checks
// every value again (ADR 0035); this only turns typing into the column's type.
import type { TFunction } from "i18next";

import { fold } from "@/lib/text";

import type { CellView, CellValue, ColumnView, DataType } from "./api";

export const CHOICE_TYPES: readonly DataType[] = ["enum", "multi_enum"];

/** The cell as text: what the grid shows, filters on and groups by. */
export function cellText(
  column: ColumnView,
  cell: CellView | undefined,
  t: TFunction,
  locale: string,
): string {
  if (!cell) return "";
  if (cell.kept_text !== null) return cell.kept_text;
  return valueText(column, cell.value, t, locale);
}

export function valueText(
  column: ColumnView,
  value: CellValue,
  t: TFunction,
  locale: string,
): string {
  if (value === null) return "";
  const labels = new Map(column.options.map((o) => [o.id, o.label]));
  switch (column.data_type) {
    case "number":
      return typeof value === "number" ? new Intl.NumberFormat(locale).format(value) : "";
    case "bool":
      return value === true ? t("matrix.yes") : value === false ? t("matrix.no") : "";
    case "enum":
      return typeof value === "string" ? (labels.get(value) ?? "") : "";
    case "multi_enum":
      return Array.isArray(value) ? value.map((id) => labels.get(id) ?? "").join(", ") : "";
    case "text":
      return typeof value === "string" ? value : "";
  }
}

/** The text an editor starts with: a number without grouping, so it reads back the same. */
export function editText(column: ColumnView, cell: CellView | undefined, locale: string): string {
  if (!cell) return "";
  if (cell.kept_text !== null) return cell.kept_text;
  if (column.data_type === "number" && typeof cell.value === "number") {
    return new Intl.NumberFormat(locale, { useGrouping: false, maximumFractionDigits: 20 }).format(
      cell.value,
    );
  }
  return typeof cell.value === "string" ? cell.value : "";
}

export type Parsed = { ok: true; value: CellValue } | { ok: false };

/** A number typed in the user's language: "1.420" is 1420 in Turkish and 1.42 in English. */
export function parseNumber(text: string, locale: string): Parsed {
  const compact = text.replace(/[\s\u00a0]/g, "");
  if (compact === "") return { ok: true, value: null };
  const decimal = new Intl.NumberFormat(locale).format(1.5).includes(",") ? "," : ".";
  const group = decimal === "," ? "." : ",";
  const pattern = new RegExp(`^[+-]?(\\d{1,3}(\\${group}\\d{3})+|\\d+)(\\${decimal}\\d+)?$`);
  if (!pattern.test(compact)) {
    // The other notation without grouping, e.g. "2.5" typed in Turkish.
    if (/^[+-]?\d+([.,]\d+)?$/.test(compact) && !/[.,]\d{3}$/.test(compact)) {
      return { ok: true, value: Number(compact.replace(",", ".")) };
    }
    return { ok: false };
  }
  const plain = compact.split(group).join("").replace(decimal, ".");
  const value = Number(plain);
  return Number.isFinite(value) ? { ok: true, value } : { ok: false };
}

/** Typing into a text or number cell. Choices and yes/no have their own editors. */
export function parseInput(column: ColumnView, text: string, locale: string): Parsed {
  if (column.data_type === "number") return parseNumber(text, locale);
  const trimmed = text.trim();
  return { ok: true, value: trimmed === "" ? null : trimmed };
}

/** Whether a row matches the filter: folded words, each in the title, authors or a cell. */
export function matches(haystack: string, filter: string): boolean {
  const words = fold(filter).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const folded = fold(haystack);
  return words.every((word) => folded.includes(word));
}

/** The groups a row falls in under a choice or yes/no column: one per choice it has. */
export function groupKeys(column: ColumnView, cell: CellView | undefined): string[] {
  if (!cell) return [""];
  if (cell.kept_text !== null || cell.value === null) return [""];
  if (column.data_type === "bool") return [cell.value === true ? "yes" : "no"];
  if (column.data_type === "enum" && typeof cell.value === "string") return [cell.value];
  if (column.data_type === "multi_enum" && Array.isArray(cell.value) && cell.value.length > 0) {
    return cell.value;
  }
  return [""];
}
