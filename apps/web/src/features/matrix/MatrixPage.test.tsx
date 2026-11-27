// Task 52: the matrix grid. Editing by keyboard, undo, filter, grouping, a type change that
// keeps cells it cannot convert, and the papers excluded after their cells were written.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import {
  fakeBackend,
  matrixColumn,
  matrixRow,
  matrixView,
  readyPlatform,
  review,
  type FakeBackend,
} from "@/test/fakeBackend";

import { parseNumber } from "./values";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: false });
  useActiveReviewStore.setState({ activeReviewId: null });
  // jsdom has no layout; the virtualized rows need a size to decide which to draw.
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(1200);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {
        return undefined;
      }
      unobserve() {
        return undefined;
      }
      disconnect() {
        return undefined;
      }
    },
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const METHOD = matrixColumn({
  id: "method",
  name: "Method",
  data_type: "enum",
  options: [
    { id: "survey", label: "Survey" },
    { id: "interview", label: "Interview" },
  ],
});
const SIZE = matrixColumn({ id: "size", name: "Sample", data_type: "number", sort_order: 1 });
const NOTES = matrixColumn({ id: "notes", name: "Findings", sort_order: 2 });

function setUp(prepare?: (backend: FakeBackend) => void) {
  window.location.hash = "#/matrix";
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  backend.matrices.push(
    matrixView({
      columns: [METHOD, SIZE, NOTES],
      rows: [
        matrixRow({ paper_id: "p1", title: "Birds at night", first_author: "Yılmaz" }),
        matrixRow({
          paper_id: "p2",
          title: "Frogs in spring",
          first_author: "Smith",
          cells: [cell("method", "interview"), cell("size", null, "1.420")],
        }),
        matrixRow({
          paper_id: "p3",
          title: "Owls",
          first_author: "Kaya",
          cells: [cell("method", "survey")],
        }),
      ],
    }),
  );
  prepare?.(backend);
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

function cell(column: string, value: unknown, kept: string | null = null) {
  return {
    column_id: column,
    value: value as never,
    kept_text: kept,
    origin: "manual" as const,
    updated_at: "2026-11-26T10:00:00Z",
    evidence: [],
  };
}

const cellsOf = (backend: FakeBackend, paperId: string) =>
  backend.matrices[0]?.rows.find((r) => r.paper_id === paperId)?.cells ?? [];

async function grid() {
  return screen.findByRole("grid", { name: "Literature matrix" });
}

function cellAt(table: HTMLElement, title: string, column: number) {
  const row = within(table)
    .getAllByRole("row")
    .find((r) => r.textContent.includes(title));
  if (!row) throw new Error(`no row ${title}`);
  const found = within(row).getAllByRole("gridcell")[column];
  if (!found) throw new Error("no cell");
  return found;
}

describe("the matrix", () => {
  it("offers to create one, then asks for the first column", async () => {
    const { backend, user } = setUp((b) => {
      b.matrices = [];
    });
    await user.click(await screen.findByRole("button", { name: "Create a matrix" }));
    expect(await screen.findByText(/No columns yet/)).toBeInTheDocument();
    expect(backend.matrices[0]?.name).toBe("Literature matrix");

    await user.click(screen.getByRole("button", { name: "Add column" }));
    const dialog = await screen.findByRole("dialog", { name: "Add column" });
    await user.type(within(dialog).getByRole("textbox", { name: "Name" }), "Design");
    await user.click(within(dialog).getByRole("radio", { name: "Several choices" }));
    await user.click(within(dialog).getByRole("button", { name: "Add a choice" }));
    await user.type(within(dialog).getByRole("textbox", { name: "Choice 1" }), "Survey");
    await user.click(within(dialog).getByRole("button", { name: "Add column" }));
    await waitFor(() => {
      expect(backend.matrices[0]?.columns[0]).toMatchObject({
        name: "Design",
        data_type: "multi_enum",
        options: [{ label: "Survey" }],
      });
    });
  });

  it("is edited from the keyboard, and undo puts back what was there", async () => {
    const { backend, user } = setUp();
    const table = await grid();
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Paper", "Method", "Sample", "Findings"]);
    table.focus();
    // The first cell is active; two steps right is "Findings"; typing starts the edit.
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(cellAt(table, "Birds at night", 2)).toHaveAttribute("aria-selected", "true");
    await user.keyboard("Calls peak at dusk{Enter}");
    await waitFor(() => {
      expect(cellsOf(backend, "p1")).toContainEqual(
        expect.objectContaining({ column_id: "notes", value: "Calls peak at dusk" }),
      );
    });
    // Enter moved down: the next row's cell is active.
    expect(cellAt(table, "Frogs in spring", 2)).toHaveAttribute("aria-selected", "true");

    // A number typed the Turkish or English way; here English.
    await user.keyboard("{ArrowLeft}{Enter}");
    const editor = within(table).getByRole("textbox", { name: "Edit Sample" });
    expect(editor).toHaveValue("1.420");
    await user.clear(editor);
    await user.type(editor, "1,420{Enter}");
    await waitFor(() => {
      expect(cellsOf(backend, "p2")).toContainEqual(
        expect.objectContaining({ column_id: "size", value: 1420, kept_text: null }),
      );
    });

    // Undo twice: the kept text comes back, then the empty cell.
    await user.keyboard("{Control>}z{/Control}");
    await waitFor(() => {
      expect(cellsOf(backend, "p2")).toContainEqual(
        expect.objectContaining({ column_id: "size", value: null, kept_text: "1.420" }),
      );
    });
    await user.keyboard("{Control>}z{/Control}");
    await waitFor(() => {
      expect(cellsOf(backend, "p1").some((c) => c.column_id === "notes")).toBe(false);
    });
    // And redo.
    await user.keyboard("{Control>}y{/Control}");
    await waitFor(() => {
      expect(cellsOf(backend, "p1")).toContainEqual(
        expect.objectContaining({ column_id: "notes", value: "Calls peak at dusk" }),
      );
    });
  });

  it("picks a choice, clears with Delete, and refuses what is not a number", async () => {
    const { backend, user } = setUp();
    const table = await grid();
    table.focus();
    await user.keyboard("{Enter}");
    await user.selectOptions(
      within(table).getByRole("combobox", { name: "Edit Method" }),
      "Survey",
    );
    await user.keyboard("{Enter}");
    await waitFor(() => {
      expect(cellsOf(backend, "p1")).toContainEqual(
        expect.objectContaining({ column_id: "method", value: "survey" }),
      );
    });
    // Now on the second row: Delete clears its choice.
    await user.keyboard("{Delete}");
    await waitFor(() => {
      expect(cellsOf(backend, "p2").some((c) => c.column_id === "method")).toBe(false);
    });

    await user.keyboard("{ArrowRight}x");
    const editor = within(table).getByRole("textbox", { name: "Edit Sample" });
    await user.keyboard("{Enter}");
    expect(await within(table).findByRole("alert")).toHaveTextContent("Not a number.");
    expect(editor).toHaveAttribute("aria-invalid", "true");
    await user.keyboard("{Escape}");
    expect(within(table).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("marks a cell a type change could not convert", async () => {
    setUp();
    const table = await grid();
    const kept = cellAt(table, "Frogs in spring", 1);
    expect(kept).toHaveAttribute("aria-invalid", "true");
    expect(within(kept).getByLabelText(/Not converted/)).toBeInTheDocument();
    expect(kept).toHaveTextContent("1.420");
  });

  it("filters, sorts and groups the rows", async () => {
    const { user } = setUp();
    const table = await grid();
    const titles = () =>
      within(table)
        .getAllByRole("rowheader")
        // A paper's title, or a group's name and size.
        .map((h) => h.querySelector("span")?.textContent ?? h.textContent);
    await user.type(screen.getByRole("searchbox", { name: "Filter rows" }), "yilmaz");
    await waitFor(() => {
      expect(titles()).toHaveLength(1);
    });
    expect(titles()[0]).toContain("Birds at night");
    await user.clear(screen.getByRole("searchbox", { name: "Filter rows" }));

    await user.selectOptions(screen.getByRole("combobox", { name: "Group by" }), "Method");
    await waitFor(() => {
      expect(titles().map((t) => t.split(" · ")[0])).toEqual([
        "Survey",
        "Owls",
        "Interview",
        "Frogs in spring",
        "Empty",
        "Birds at night",
      ]);
    });

    await user.selectOptions(screen.getByRole("combobox", { name: "Group by" }), "No grouping");
    await user.click(screen.getByRole("button", { name: "Column Method: menu" }));
    await user.click(await screen.findByRole("menuitem", { name: "Sort A to Z" }));
    await waitFor(() => {
      expect(titles().map((t) => t.slice(0, 5))).toEqual(["Frogs", "Owls", "Birds"]);
    });
  });

  it("shows excluded papers' kept cells only when asked, and does not edit them", async () => {
    const { user } = setUp((b) => {
      b.matrices[0]?.rows.push(
        matrixRow({
          paper_id: "p4",
          title: "Left out",
          included: false,
          cells: [cell("notes", "Kept")],
        }),
      );
    });
    const table = await grid();
    expect(within(table).queryByText("Left out")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("checkbox", { name: "Show 1 excluded paper whose cells are kept" }),
    );
    const kept = cellAt(table, "Left out", 2);
    expect(kept).toHaveTextContent("Kept");
    expect(kept).toHaveAttribute("aria-readonly", "true");
    await user.dblClick(kept);
    expect(within(table).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("asks before deleting a column", async () => {
    const { backend, user } = setUp();
    await grid();
    await user.click(screen.getByRole("button", { name: "Column Findings: menu" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete column" }));
    const ask = await screen.findByRole("alertdialog", { name: "Delete the column “Findings”?" });
    await user.click(within(ask).getByRole("button", { name: "Delete column" }));
    await waitFor(() => {
      expect(backend.matrices[0]?.columns.map((c) => c.id)).toEqual(["method", "size"]);
    });
  });
});

describe("numbers typed in the user's language", () => {
  it.each([
    ["en", "1,420", 1420],
    ["en", "1.42", 1.42],
    ["tr", "1.420", 1420],
    ["tr", "1,42", 1.42],
    ["tr", "2.5", 2.5],
    ["en", "", null],
  ])("%s %s", (locale, text, value) => {
    expect(parseNumber(text, locale)).toEqual({ ok: true, value });
  });

  it.each(["12a", "1,2,3", "--4"])("not %s", (text) => {
    expect(parseNumber(text, "en")).toEqual({ ok: false });
  });
});
