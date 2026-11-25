// Task 33: full-text screening shows the PDF beside the criteria; without one, "Find PDFs"
// and "Full text not retrieved", which is a state of its own.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import type { PdfDocument } from "@/lib/pdf";
import { fakeBackend, readyPlatform, review } from "@/test/fakeBackend";
import { fakeScreening } from "@/test/fakeScreening";

import { useScreeningSession } from "./store";

vi.mock("@/lib/pdf", () => ({
  openPdf: (): Promise<PdfDocument> =>
    Promise.resolve({
      numPages: 3,
      pageSize: () =>
        Promise.resolve({ width: 600, height: 800, transform: [1, 0, 0, -1, 0, 800] as const }),
      renderPage: () => ({ done: Promise.resolve(), dispose: () => undefined }),
      renderThumbnail: () => ({ done: Promise.resolve(), dispose: () => undefined }),
      outline: () => Promise.resolve([]),
      destroy: () => Promise.resolve(),
    }),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: false, inspectorOpen: false });
  useActiveReviewStore.setState({ activeReviewId: null });
  useScreeningSession.setState({ decided: 0, done: [], pendingNotes: {} });
  window.location.hash = "#/screening?stage=full_text";
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(900);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(600);
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

function open() {
  const backend = fakeBackend({ language: "en" });
  backend.reviews = [review({ id: "review-1" })];
  const screening = fakeScreening(backend, "review-1", [
    {
      paper_id: "with-pdf",
      title: "A paper with its PDF",
      attachments: [
        {
          id: "att-1",
          paper_id: "with-pdf",
          kind: "pdf",
          file_name: "with-pdf.pdf",
          sha256: "a".repeat(64),
          size: 1000,
          page_count: 3,
          text_status: "ok",
          error: null,
          source: "manual",
          created_at: "2026-11-16T00:00:00+00:00",
        },
      ],
    },
    { paper_id: "no-pdf", title: "A paper without a PDF" },
  ]);
  // Both passed title-abstract screening.
  for (const paperId of ["with-pdf", "no-pdf"]) {
    screening.decisions.push({
      id: `ta-${paperId}`,
      paper_id: paperId,
      stage: "title_abstract",
      decision: "include",
      criterion_id: null,
      note: null,
      reviewer: "owner",
      supersedes_id: null,
      created_at: "2026-11-16T00:00:00+00:00",
    });
  }
  render(<App platform={readyPlatform} fetch={screening.fetch} />);
  return { backend, screening, user: userEvent.setup() };
}

describe("full-text screening", () => {
  it("opens the record's PDF beside the criteria and the decision bar", async () => {
    open();

    const pane = await screen.findByRole("region", { name: "Full text" });
    // The reader's own toolbar, inside the full-text pane.
    expect(await within(pane).findByRole("textbox", { name: "Page" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 1, name: "A paper with its PDF" })).toBeVisible();
    expect(screen.getByRole("toolbar", { name: "Decision" })).toBeVisible();
  });

  it("offers Find PDFs and records 'not retrieved' as its own state", async () => {
    const { backend, screening, user } = open();
    await screen.findByRole("heading", { level: 1, name: "A paper with its PDF" });
    await user.keyboard("j");
    const pane = await screen.findByRole("region", { name: "Full text" });
    await within(pane).findByRole("heading", { name: "No PDF for this record" });

    await user.click(within(pane).getByRole("button", { name: "Find PDFs" }));
    expect(await within(pane).findByRole("status")).toHaveTextContent(
      "No free source is known for this record.",
    );
    expect(backend.requests.find((r) => r.path === "/pdfs/open-access")?.body).toEqual({
      paper_ids: ["no-pdf"],
    });

    await user.click(screen.getByRole("button", { name: "Full text not retrieved" }));

    await waitFor(() => {
      expect(screening.decisions.at(-1)).toMatchObject({
        paper_id: "no-pdf",
        stage: "full_text",
        decision: "not_retrieved",
      });
    });
    await user.selectOptions(screen.getByRole("combobox", { name: "Show" }), "Not retrieved (1)");
    expect(
      await screen.findByRole("heading", { level: 1, name: "A paper without a PDF" }),
    ).toBeVisible();
  });
});
