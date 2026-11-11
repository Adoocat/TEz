import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import {
  fakeBackend,
  overview,
  readyPlatform,
  resultRow,
  review,
  type FakeBackend,
} from "@/test/fakeBackend";

import { availableOptions, filterRows, mergeReasons, noFilters } from "./filters";
import { ROW_HEIGHT } from "./ResultList";
import { useSearchView } from "./store";

const VIEWPORT = 600;

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useSearchView.setState({ activeSearchId: null, selectedPaperId: null });
  window.location.hash = "#/search";
  // jsdom has no layout; the list needs a size to decide which rows to draw.
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(VIEWPORT);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(800);
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

function open(backend: FakeBackend) {
  return render(<App platform={readyPlatform} fetch={backend.fetch} />);
}

const withReview = () => {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  return backend;
};

async function startSearch(backend: FakeBackend, query = '"code review" AND LLM') {
  const user = userEvent.setup();
  open(backend);
  await user.type(await screen.findByRole("textbox", { name: "Search query" }), query);
  await user.click(screen.getByRole("button", { name: "Search" }));
  await waitFor(() => {
    expect(backend.requests.some((r) => r.path === "/searches/search-1/events")).toBe(true);
  });
  return user;
}

describe("the review a search belongs to", () => {
  it("is created first when there is none", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "en" });
    open(backend);

    expect(await screen.findByText(/Searches belong to a review/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "LLM Kod İnceleme SLR");
    await user.click(screen.getByRole("radio", { name: "PRISMA 2020" }));
    await user.click(screen.getByRole("button", { name: "Create review" }));

    expect(await screen.findByRole("textbox", { name: "Search query" })).toBeInTheDocument();
    expect(backend.reviews).toMatchObject([
      { title: "LLM Kod İnceleme SLR", method: "prisma2020" },
    ]);
    expect(screen.getByRole("combobox", { name: "Active review" })).toHaveDisplayValue(
      "LLM Kod İnceleme SLR",
    );
  });

  it("is sent with the search, and can be switched in the title bar", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.reviews.push(review({ id: "r2", title: "Second review" }));
    open(backend);

    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Active review" }),
      "Second review",
    );
    await user.type(screen.getByRole("textbox", { name: "Search query" }), "llm");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/searches")?.body).toMatchObject({
        review_id: "r2",
      });
    });
  });
});

describe("the query form", () => {
  it("sends the query, the chosen sources and the years", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    open(backend);

    await user.type(await screen.findByRole("textbox", { name: "Search query" }), "llm");
    await user.click(screen.getByRole("button", { name: /^arXiv/ }));
    await user.type(screen.getByRole("textbox", { name: "From" }), "2020");
    await user.type(screen.getByRole("textbox", { name: "To" }), "2024");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/searches")?.body).toEqual({
        review_id: "review-1",
        query: "llm",
        sources: ["openalex", "semantic_scholar", "crossref"],
        year_from: 2020,
        year_to: 2024,
        limit: 1000,
      });
    });
  });

  it("cannot start without a query, a source or sensible years", async () => {
    const user = userEvent.setup();
    open(withReview());

    const start = await screen.findByRole("button", { name: "Search" });
    expect(start).toBeDisabled();

    await user.type(screen.getByRole("textbox", { name: "Search query" }), "llm");
    expect(start).toBeEnabled();

    await user.type(screen.getByRole("textbox", { name: "From" }), "2024");
    await user.type(screen.getByRole("textbox", { name: "To" }), "2020");
    expect(start).toBeDisabled();
    await user.clear(screen.getByRole("textbox", { name: "To" }));
    expect(start).toBeEnabled();

    for (const name of [/^OpenAlex/, /^Semantic Scholar/, /^arXiv/, /^Crossref/]) {
      await user.click(screen.getByRole("button", { name }));
    }
    expect(start).toBeDisabled();
  });

  it("does not offer DBLP, which blocks API clients for now", async () => {
    open(withReview());

    await screen.findByRole("textbox", { name: "Search query" });
    expect(screen.queryByRole("button", { name: /DBLP/ })).not.toBeInTheDocument();
  });
});

describe("each source's state", () => {
  it("is shown separately, and a failure leaves the others alone", async () => {
    const backend = withReview();
    await startSearch(backend);

    act(() => {
      backend.emitSource("search-1", { source: "openalex", state: "searching" });
      backend.emitSource("search-1", {
        source: "crossref",
        state: "rate_limited",
        wait_seconds: 12,
      });
    });
    expect(await screen.findByRole("button", { name: /^OpenAlex.*searching/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /^Crossref.*wait 12 s/i })).toBeVisible();

    backend.searchOverview = overview({
      runs: [
        {
          source: "openalex",
          status: "partial",
          translated_query: "q-oa",
          executed_at: "2026-11-04T10:00:00+00:00",
          total_reported: 500,
          retrieved_count: 100,
          error: { code: "source.key_required", params: { source: "openalex" } },
        },
        {
          source: "arxiv",
          status: "error",
          translated_query: "q-ax",
          executed_at: "2026-11-04T10:00:00+00:00",
          total_reported: null,
          retrieved_count: 0,
          error: { code: "source.timeout", params: { source: "arxiv" } },
        },
        {
          source: "crossref",
          status: "ok",
          translated_query: "q-cr",
          executed_at: "2026-11-04T10:00:00+00:00",
          total_reported: 42,
          retrieved_count: 42,
          error: null,
        },
      ],
    });
    act(() => {
      backend.emitSource("search-1", { source: "crossref", state: "done", retrieved: 42 });
      backend.finishSearch("search-1");
    });

    expect(await screen.findByRole("button", { name: /^Crossref.*42 results/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /^OpenAlex.*100 results, partial/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /^arXiv.*failed/ })).toBeVisible();
    expect(screen.getByText(/did not answer in time/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Add a key" })).toHaveAttribute(
      "href",
      "#/settings/sources",
    );
  });

  it("shows the query each source was really sent", async () => {
    const backend = withReview();
    backend.searchOverview = overview();
    await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    expect(await screen.findByText("Queries sent to each source")).toBeInTheDocument();
    expect(screen.getByText('all:"code review" AND all:LLM')).toBeInTheDocument();
  });
});

describe("results", () => {
  it("Task 14 acceptance: 1000 results draw only what is on screen", async () => {
    const backend = withReview();
    backend.searchResults = Array.from({ length: 1000 }, (_, i) =>
      resultRow({ paper_id: `p${String(i)}`, title: `Paper number ${String(i)}` }),
    );
    backend.searchOverview = overview({ retrieved: 1000, unique: 1000, duplicates: 0 });
    await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    const list = await screen.findByRole("list", { name: "Results" });
    await within(list).findByText("Paper number 0");
    const drawn = () => within(list).getAllByRole("listitem").length;
    expect(drawn()).toBeLessThan(30);
    expect(list.style.height).toBe(`${String(1000 * ROW_HEIGHT)}px`);
    expect(screen.queryByText("Paper number 500")).not.toBeInTheDocument();

    const scroller = screen.getByTestId("result-scroller");
    Object.defineProperty(scroller, "scrollTop", { value: 500 * ROW_HEIGHT, configurable: true });
    act(() => {
      scroller.dispatchEvent(new Event("scroll"));
    });

    expect(await within(list).findByText("Paper number 500")).toBeInTheDocument();
    expect(drawn()).toBeLessThan(30);
    expect(screen.queryByText("Paper number 0")).not.toBeInTheDocument();
    expect(within(list).getAllByRole("listitem")[0]).toHaveAttribute("aria-setsize", "1000");
  });

  it("show the counts of the search", async () => {
    const backend = withReview();
    backend.searchResults = [resultRow()];
    backend.searchOverview = overview({
      retrieved: 1912,
      duplicates: 487,
      unique: 1425,
      in_library: 312,
    });
    await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    expect(
      await screen.findByText(/1,912 records.*487 duplicates.*1,425 unique.*312 already/),
    ).toBeVisible();
  });

  it("mark what was merged and what is already kept", async () => {
    const backend = withReview();
    backend.searchResults = [
      resultRow({
        in_library: true,
        in_review: true,
        oa_url: "https://example.org/a.pdf",
        sources: [
          { source: "openalex", rank: 1, match_method: "new", match_score: null },
          { source: "crossref", rank: 2, match_method: "doi", match_score: 1 },
        ],
      }),
    ];
    backend.searchOverview = overview();
    await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    const list = await screen.findByRole("list", { name: "Results" });
    expect(await within(list).findByText("2 records merged")).toBeVisible();
    expect(within(list).getByText("In library")).toBeVisible();
    expect(within(list).getByText("In review")).toBeVisible();
    expect(within(list).getByText("Open access")).toBeVisible();
  });

  it("can be added to the review and the library", async () => {
    const backend = withReview();
    backend.searchResults = [
      resultRow({ paper_id: "p1", title: "First" }),
      resultRow({ paper_id: "p2", title: "Second" }),
    ];
    backend.searchOverview = overview();
    const user = await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    await user.click(await screen.findByRole("checkbox", { name: "Select: First" }));
    await user.click(screen.getByRole("button", { name: "Add to review (1)" }));
    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/reviews/review-1/records")?.body).toEqual({
        paper_ids: ["p1"],
        search_id: "search-1",
      });
    });
    expect(await screen.findByText("1 added, 0 already there")).toBeVisible();

    await user.click(screen.getByRole("checkbox", { name: "Select all" }));
    await user.click(screen.getByRole("button", { name: "Add to library (2)" }));
    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/library/papers")?.body).toEqual({
        paper_ids: ["p1", "p2"],
      });
    });
  });

  it("can have their free PDFs looked for in the background", async () => {
    const backend = withReview();
    backend.searchResults = [
      resultRow({ paper_id: "p1", title: "First" }),
      resultRow({ paper_id: "p2", title: "Second" }),
    ];
    backend.searchOverview = overview();
    const user = await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    await user.click(await screen.findByRole("checkbox", { name: "Select all" }));
    await user.click(screen.getByRole("button", { name: "Find PDFs (2)" }));

    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/pdfs/open-access")?.body).toEqual({
        paper_ids: ["p1", "p2"],
      });
    });
    expect(
      await screen.findByText(
        "1 downloads queued · 0 already have a PDF · 1 have no DOI, arXiv id or link",
      ),
    ).toBeVisible();
  });

  it("can be filtered by open access", async () => {
    const backend = withReview();
    backend.searchResults = [
      resultRow({ paper_id: "p1", title: "Closed" }),
      resultRow({ paper_id: "p2", title: "Open", oa_url: "https://example.org/p.pdf" }),
    ];
    backend.searchOverview = overview();
    const user = await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    await screen.findByText("Closed");
    await user.click(screen.getByRole("checkbox", { name: "Open access only" }));

    expect(screen.queryByText("Closed")).not.toBeInTheDocument();
    expect(screen.getByText("Open")).toBeVisible();
  });

  it("show details in the inspector, including how records were merged", async () => {
    const backend = withReview();
    backend.searchResults = [
      resultRow({
        title: "Selected paper",
        abstract: "An abstract worth reading.",
        doi: "10.1000/abc",
        sources: [
          { source: "openalex", rank: 3, match_method: "new", match_score: null },
          { source: "arxiv", rank: 9, match_method: "title_fuzzy", match_score: 0.97 },
        ],
      }),
    ];
    backend.searchOverview = overview();
    const user = await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    await user.click(await screen.findByRole("button", { name: /Selected paper/ }));

    const inspector = screen.getByRole("complementary", { name: "Inspector" });
    expect(within(inspector).getByText("An abstract worth reading.")).toBeVisible();
    expect(within(inspector).getByRole("link", { name: "10.1000/abc" })).toHaveAttribute(
      "href",
      "https://doi.org/10.1000/abc",
    );
    expect(within(inspector).getByText(/title similarity.*%97/i)).toBeVisible();
  });

  it("say so when nothing was found", async () => {
    const backend = withReview();
    backend.searchOverview = overview();
    await startSearch(backend);
    act(() => {
      backend.finishSearch("search-1");
    });

    expect(await screen.findByText("No results.")).toBeVisible();
  });
});

describe("history", () => {
  it("lists earlier searches and opens one", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.searchHistory = [
      overview({
        search_id: "old-search",
        query: '"code review" AND LLM',
        filters: { year_from: 2020, year_to: null },
      }),
    ];
    backend.searchOverview = overview({ search_id: "old-search" });
    backend.searchResults = [resultRow({ title: "From the old search" })];
    open(backend);

    await user.click(await screen.findByRole("radio", { name: "History" }));
    expect(await screen.findByText("2020 – …")).toBeVisible();
    expect(screen.getByText(/Crossref/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: '"code review" AND LLM' }));

    expect(await screen.findByText("From the old search")).toBeVisible();
    expect(backend.requests.some((r) => r.path === "/searches/old-search/results")).toBe(true);
  });

  it("says so when empty", async () => {
    const user = userEvent.setup();
    open(withReview());

    await user.click(await screen.findByRole("radio", { name: "History" }));

    expect(await screen.findByText(/No searches in this review yet/)).toBeVisible();
  });
});

describe("in Turkish", () => {
  it("the screen speaks Turkish", async () => {
    const backend = fakeBackend({ language: "tr" });
    backend.reviews.push(review());
    open(backend);

    expect(await screen.findByRole("textbox", { name: "Arama sorgusu" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Ara" })).toBeDisabled();
  });
});

describe("filters", () => {
  const rows = [
    resultRow({ paper_id: "a", venue_type: "journal", language: "en" }),
    resultRow({ paper_id: "b", venue_type: "preprint", language: "tr", oa_url: "https://x.org/b" }),
    resultRow({ paper_id: "c", venue_type: null, language: null }),
  ];
  const ids = (found: typeof rows) => found.map((row) => row.paper_id);

  it("pass everything by default", () => {
    expect(ids(filterRows(rows, noFilters))).toEqual(["a", "b", "c"]);
  });

  it("narrow by type, language and open access", () => {
    expect(ids(filterRows(rows, { ...noFilters, venueType: "journal" }))).toEqual(["a"]);
    expect(ids(filterRows(rows, { ...noFilters, language: "tr" }))).toEqual(["b"]);
    expect(ids(filterRows(rows, { ...noFilters, openAccessOnly: true }))).toEqual(["b"]);
  });

  it("offer only what is present", () => {
    expect(availableOptions(rows)).toEqual({
      venueTypes: ["journal", "preprint"],
      languages: ["en", "tr"],
    });
  });

  it("name how duplicates were recognized", () => {
    const merged = resultRow({
      sources: [
        { source: "a", rank: 1, match_method: "new", match_score: null },
        { source: "b", rank: 1, match_method: "title_fuzzy", match_score: 0.95 },
      ],
    });

    expect(mergeReasons(merged)).toEqual([{ method: "title_fuzzy", score: 0.95 }]);
  });
});
