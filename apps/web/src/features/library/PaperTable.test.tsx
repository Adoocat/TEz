import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import {
  fakeBackend,
  libraryPaper,
  paperDetail,
  readyPlatform,
  type FakeBackend,
} from "@/test/fakeBackend";

import { applyFilters, noLibraryFilters } from "./filters";
import { useLibraryView } from "./store";
import { TABLE_ROW_HEIGHT } from "./PaperTable";

const VIEWPORT = 600;

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useLibraryView.setState({ scope: { kind: "all" }, selectedPaperId: null });
  window.location.hash = "#/library";
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(VIEWPORT);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(1000);
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

function setUp(configure: (backend: FakeBackend) => void = () => undefined) {
  const backend = fakeBackend({ language: "en" });
  backend.papers = [
    libraryPaper({
      id: "a",
      title: "Alpha study",
      year: 2019,
      added_at: "2026-11-01T00:00:00+00:00",
    }),
    libraryPaper({
      id: "b",
      title: "Beta review",
      year: 2024,
      pdf: "ok",
      reading_status: "read",
      added_at: "2026-11-03T00:00:00+00:00",
    }),
    libraryPaper({
      id: "c",
      title: "Gamma survey",
      year: 2021,
      added_at: "2026-11-02T00:00:00+00:00",
    }),
  ];
  configure(backend);
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

function titles() {
  const table = screen.getByRole("table", { name: "Papers" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[2]?.textContent);
}

describe("the library table", () => {
  it("lists the newest additions first and sorts by a column", async () => {
    const { user } = setUp();
    await screen.findByText("Alpha study");
    expect(titles()).toEqual(["Beta review", "Gamma survey", "Alpha study"]);

    await user.click(screen.getByRole("button", { name: "Year" }));
    expect(titles()).toEqual(["Alpha study", "Gamma survey", "Beta review"]);
    expect(screen.getByRole("columnheader", { name: "Year" })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );

    await user.click(screen.getByRole("button", { name: "Year" }));
    expect(titles()).toEqual(["Beta review", "Gamma survey", "Alpha study"]);
  });

  it("searches through the backend and shows hits best first", async () => {
    const { user, backend } = setUp((b) => {
      b.searchHits = { surv: ["c", "a"] };
    });
    await screen.findByText("Alpha study");

    await user.type(screen.getByRole("searchbox", { name: "Search the library" }), "surv");

    await waitFor(() => {
      expect(titles()).toEqual(["Gamma survey", "Alpha study"]);
    });
    expect(screen.getByText("2 of 3 papers shown")).toBeInTheDocument();
    expect(backend.requests.some((r) => r.path === "/papers/search")).toBe(true);

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(titles()).toHaveLength(3);
    });
  });

  it("filters by year, reading status and PDF", async () => {
    const { user } = setUp();
    await screen.findByText("Alpha study");

    await user.type(screen.getByRole("textbox", { name: "From" }), "2020");
    expect(titles()).toEqual(["Beta review", "Gamma survey"]);
    await user.selectOptions(screen.getByRole("combobox", { name: "PDF" }), "No PDF");
    expect(titles()).toEqual(["Gamma survey"]);
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(titles()).toHaveLength(3);
    await user.selectOptions(screen.getByRole("combobox", { name: "Reading status" }), "Read");
    expect(titles()).toEqual(["Beta review"]);
  });

  it("draws only the rows on screen for 2000 papers", async () => {
    setUp((backend) => {
      backend.papers = Array.from({ length: 2000 }, (_, index) =>
        libraryPaper({ id: `p${String(index)}`, title: `Paper ${String(index)}` }),
      );
    });

    await screen.findByText("2000 papers");
    const drawn = within(screen.getByRole("table", { name: "Papers" })).getAllByRole("row");
    expect(drawn.length).toBeLessThan(VIEWPORT / TABLE_ROW_HEIGHT + 25);
  });
});

describe("the inspector", () => {
  it("shows the selected paper and edits its citation key", async () => {
    const { user, backend } = setUp((b) => {
      b.details = {
        b: paperDetail({
          id: "b",
          title: "Beta review",
          related: [
            { paper_id: "x", title: "Beta review", year: 2025, relation: "published_version" },
          ],
          attachments: [
            {
              id: "att",
              paper_id: "b",
              kind: "pdf",
              file_name: "beta.pdf",
              sha256: "f".repeat(64),
              size: 2 * 1024 * 1024,
              page_count: 12,
              text_status: "needs_ocr",
              error: null,
              source: "manual",
              created_at: "2026-11-03T00:00:00+00:00",
            },
          ],
        }),
      };
    });
    await user.click(await screen.findByText("Beta review"));

    const inspector = screen.getByRole("complementary", { name: "Inspector" });
    expect(await within(inspector).findByRole("heading", { name: "Beta review" })).toBeVisible();
    expect(within(inspector).getByText("Ayşe Yılmaz")).toBeVisible();
    expect(within(inspector).getByText("10.1145/1")).toBeVisible();
    expect(
      within(inspector).getByText("A published version is in the library: Beta review (2025)"),
    ).toBeVisible();

    await user.click(within(inspector).getByRole("radio", { name: "Files (1)" }));
    expect(within(inspector).getByText("12 pages · 2 MB · Scanned PDF (needs OCR)")).toBeVisible();

    await user.click(within(inspector).getByRole("button", { name: "Edit the citation key" }));
    const field = within(inspector).getByRole("textbox", { name: "Key" });
    await user.clear(field);
    await user.type(field, "taken{Enter}");
    expect(await within(inspector).findByRole("alert")).toHaveTextContent(
      "Another paper already has the key taken.",
    );
    await user.clear(field);
    await user.type(field, "beta2024{Enter}");
    await waitFor(() => {
      expect(
        backend.requests.filter((r) => r.path === "/papers/b" && r.method === "PATCH").at(-1)?.body,
      ).toEqual({ citekey: "beta2024" });
    });
  });
});

describe("filters", () => {
  it("keep the order of search hits", () => {
    const rows = [libraryPaper({ id: "a" }), libraryPaper({ id: "b" })];
    expect(applyFilters(rows, noLibraryFilters, ["b", "a", "gone"]).map((r) => r.id)).toEqual([
      "b",
      "a",
    ]);
  });
});
