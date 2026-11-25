import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, libraryPaper, readyPlatform } from "@/test/fakeBackend";

import { useLibraryView } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useActiveReviewStore.setState({ activeReviewId: null });
  useLibraryView.setState({ scope: { kind: "all" }, selectedPaperId: null });
  window.location.hash = "#/library";
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
  vi.unstubAllGlobals();
});

function hit(paperId: string, pageHits = 1) {
  return {
    paper_id: paperId,
    title: `Paper ${paperId}`,
    first_author: "Ada Lovelace",
    author_count: 2,
    year: 2024,
    page_hits: pageHits,
    pages: [
      {
        attachment_id: `pdf-${paperId}`,
        page: 7,
        snippet: [
          { text: "\u2026we used ", hit: false },
          { text: "grounded theory", hit: true },
          { text: " here", hit: false },
        ],
      },
    ],
  };
}

async function openFulltext() {
  const backend = fakeBackend({ language: "en" });
  backend.papers = [
    libraryPaper({ id: "a", title: "Paper a", year: 2024 }),
    libraryPaper({ id: "b", title: "Paper b", year: 1999 }),
  ];
  const user = userEvent.setup();
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  await user.click(await screen.findByRole("radio", { name: "Full text" }));
  return { backend, user, box: screen.getByRole("searchbox", { name: "Search the library" }) };
}

describe("full-text search", () => {
  it("shows passages with their page; a passage opens the reader there", async () => {
    const { backend, user, box } = await openFulltext();
    backend.fulltextHits = { "grounded theory": [hit("a", 3)] };
    expect(screen.getByText(/Type words to search inside the PDFs/)).toBeInTheDocument();

    await user.type(box, "grounded theory");

    const results = await screen.findByRole("list", { name: "Full-text results" });
    expect(within(results).getByText("Ada Lovelace et al. \u00b7 2024")).toBeInTheDocument();
    expect(within(results).getByText("grounded theory").tagName).toBe("MARK");
    expect(within(results).getByText("2 more pages in this paper")).toBeInTheDocument();
    expect(within(results).getByRole("link", { name: /p\. 7/ })).toHaveAttribute(
      "href",
      "#/reader/pdf-a?page=7&find=grounded+theory",
    );
  });

  it("looks only in the papers the filters leave", async () => {
    const { backend, user, box } = await openFulltext();
    backend.fulltextHits = { theory: [hit("a"), hit("b")] };
    await user.type(box, "theory");
    expect(await screen.findByText("Paper b")).toBeInTheDocument();

    await user.type(screen.getByRole("textbox", { name: "From" }), "2020");

    await waitFor(() => {
      expect(screen.queryByText("Paper b")).not.toBeInTheDocument();
    });
    const last = backend.requests.filter((r) => r.path === "/fulltext/search").at(-1);
    expect(last?.body).toEqual({ q: "theory", paper_ids: ["a"], limit: 30 });
  });

  it("selects a paper for the inspector from its title and says when nothing matches", async () => {
    const { backend, user, box } = await openFulltext();
    backend.fulltextHits = { theory: [hit("a")] };
    await user.type(box, "theory");
    await user.click(await screen.findByRole("button", { name: "Paper a" }));
    expect(useLibraryView.getState().selectedPaperId).toBe("a");

    await user.clear(box);
    await user.type(box, "zzz");
    expect(await screen.findByText(/No PDF of these papers/)).toBeInTheDocument();
  });
});
