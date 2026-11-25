// pdf.js does not run in jsdom: these tests stand in a fake document and check the reader's
// own behaviour. Real rendering, ranges and memory are checked by e2e/reader.spec.ts.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import type { OpenOptions, OutlineItem, PdfDocument } from "@/lib/pdf";
import { anchorView, fakeBackend, readyPlatform, type FakeBackend } from "@/test/fakeBackend";

import { useReaderPanel, useReaderTabs } from "./store";

const opened: OpenOptions[] = [];
const rendered: { page: number; scale: number }[] = [];
const thumbnails: number[] = [];
let outline: OutlineItem[] = [];
let failOpen = false;

vi.mock("@/lib/pdf", () => ({
  openPdf: (options: OpenOptions): Promise<PdfDocument> => {
    opened.push(options);
    if (failOpen) return Promise.reject(new Error("broken"));
    return Promise.resolve({
      numPages: 40,
      pageSize: () =>
        Promise.resolve({ width: 600, height: 800, transform: [1, 0, 0, -1, 0, 800] as const }),
      renderPage: (page, { scale }) => {
        rendered.push({ page, scale });
        return { done: Promise.resolve(), dispose: () => undefined };
      },
      renderThumbnail: (page) => {
        thumbnails.push(page);
        return { done: Promise.resolve(), dispose: () => undefined };
      },
      outline: () => Promise.resolve(outline),
      destroy: () => Promise.resolve(),
    });
  },
}));

beforeEach(() => {
  opened.length = 0;
  rendered.length = 0;
  thumbnails.length = 0;
  outline = [];
  failOpen = false;
  useReaderTabs.setState({ tabs: [], activeId: null });
  useReaderPanel.setState({ open: false, tab: "outline" });
  useLayoutStore.setState({ focus: false });
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(900);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(648);
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

function open(hash: string, prepare?: (backend: FakeBackend) => void) {
  window.location.hash = hash;
  const backend = fakeBackend({ language: "en" });
  prepare?.(backend);
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return backend;
}

describe("the reader", () => {
  it("asks to open a PDF when none is chosen", async () => {
    open("#/reader");

    expect(
      await screen.findByText("Open a PDF from the library: select a paper and choose Open PDF."),
    ).toBeInTheDocument();
  });

  it("opens the attachment's file with the token and draws only nearby pages", async () => {
    open("#/reader/att-1");

    expect(await screen.findByText("of 40")).toBeInTheDocument();
    expect(opened[0]).toEqual({
      url: "http://test/attachments/att-1/file",
      headers: { Authorization: "Bearer test-token" },
    });
    await waitFor(() => {
      expect(rendered.length).toBeGreaterThan(0);
    });
    // Fit width: (648 - 48) / 600 = 1.0
    expect(rendered[0]).toEqual({ page: 1, scale: 1 });
    expect(Math.max(...rendered.map((r) => r.page))).toBeLessThan(6);
    expect(screen.getByRole("button", { name: "Fit to width" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("zooms in steps", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1");
    await screen.findByText("of 40");

    await user.click(screen.getByRole("button", { name: "Zoom in" }));

    expect(await screen.findByText("110%")).toBeInTheDocument();
    await waitFor(() => {
      expect(rendered.at(-1)?.scale).toBe(1.1);
    });
    expect(screen.getByRole("button", { name: "Fit to width" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("says so when the PDF cannot be opened", async () => {
    failOpen = true;
    open("#/reader/att-1");

    expect(await screen.findByRole("alert")).toHaveTextContent("The PDF could not be opened.");
  });
});

describe("the reader's document panel", () => {
  it("shows the outline, marks the section being read and jumps to a page", async () => {
    const user = userEvent.setup();
    outline = [
      { title: "Introduction", page: 1, children: [] },
      {
        title: "Method",
        page: 12,
        children: [{ title: "Sampling", page: 14, children: [] }],
      },
      { title: "Project site", page: null, children: [] },
    ];
    open("#/reader/att-1");
    await user.click(await screen.findByRole("button", { name: "Outline and pages" }));

    const nav = await screen.findByRole("navigation", { name: "Outline" });
    expect(within(nav).getByRole("button", { name: /Introduction/ })).toHaveAttribute(
      "aria-current",
      "location",
    );
    expect(within(nav).getByRole("button", { name: /Sampling.*p\. 14/ })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Project site/ })).toBeDisabled();
  });

  it("says when there is no outline, and draws only the thumbnails on screen", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1");
    await user.click(await screen.findByRole("button", { name: "Outline and pages" }));
    expect(await screen.findByText("This document has no outline.")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: "Pages" }));

    expect(await screen.findByRole("button", { name: "Go to page 1" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await waitFor(() => {
      expect(thumbnails.length).toBeGreaterThan(0);
    });
    expect(Math.max(...thumbnails)).toBeLessThan(15);
  });
});

describe("search inside the document", () => {
  it("counts matches, steps through them and wraps around", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1", (backend) => {
      backend.findResults.theory = {
        text: "ready",
        pages: [
          { page: 1, matches: 2 },
          { page: 9, matches: 1 },
        ],
        total: 3,
      };
    });
    await user.click(await screen.findByRole("button", { name: "Search in this document" }));
    const box = screen.getByRole("searchbox", { name: "Search in this document" });
    expect(box).toHaveFocus();

    await user.type(box, "theory");
    expect(await screen.findByText("1 of 3")).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(screen.getByText("2 of 3")).toBeInTheDocument();
    await user.keyboard("{Shift>}{Enter}{/Shift}{Shift>}{Enter}{/Shift}");
    expect(screen.getByText("3 of 3")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  });

  it("starts from the address, at the page it names", async () => {
    open("#/reader/att-1?page=9&find=theory", (backend) => {
      backend.findResults.theory = {
        text: "ready",
        pages: [
          { page: 1, matches: 2 },
          { page: 9, matches: 1 },
        ],
        total: 3,
      };
    });

    expect(await screen.findByText("3 of 3")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Search in this document" })).toHaveValue(
      "theory",
    );
  });

  it("opens with the keyboard and says why it finds nothing", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1", (backend) => {
      backend.findResults.scan = { text: "none", pages: [], total: 0 };
    });
    await screen.findByText("of 40");

    await user.keyboard("{Control>}f{/Control}");
    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(await screen.findByText("No match")).toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "scan");
    expect(await screen.findByText("This PDF has no text to search.")).toBeInTheDocument();
  });

  it("says that a scanned PDF has no text", async () => {
    open("#/reader/att-1", (backend) => {
      backend.attachments["att-1"] = { text_status: "needs_ocr" };
    });

    expect(await screen.findByRole("note")).toHaveTextContent("This PDF has no text");
  });
});

/** Follow a link: the hash router listens to popstate. */
function go(hash: string) {
  act(() => {
    window.history.pushState(null, "", hash);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

describe("the reader's tabs and focus mode", () => {
  it("keeps open documents as tabs and returns to the last one", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1");
    const tabs = await screen.findByRole("navigation", { name: "Open documents" });
    expect(within(tabs).getByRole("link", { name: "att-1.pdf" })).toBeInTheDocument();

    go("#/reader/att-2");
    expect(await screen.findByRole("link", { name: "att-2.pdf" })).toBeInTheDocument();
    go("#/library");
    await screen.findByRole("heading", { level: 1, name: "All papers" });
    await user.click(screen.getByRole("link", { name: "Reader" }));
    expect(await screen.findByRole("heading", { name: "att-2.pdf" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close att-2.pdf" }));
    expect(await screen.findByRole("heading", { name: "att-1.pdf" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close att-1.pdf" }));
    expect(await screen.findByText(/Open a PDF from the library/)).toBeInTheDocument();
  });

  it("drops the tab of a document that is gone", async () => {
    useReaderTabs.setState({
      tabs: [{ attachmentId: "old", title: "old.pdf", page: 3 }],
      activeId: "old",
    });
    open("#/reader/old", (backend) => {
      backend.attachments.old = null;
    });

    expect(
      await screen.findByText("This document is not in the library any more."),
    ).toBeInTheDocument();
    expect(useReaderTabs.getState().tabs).toEqual([]);
  });

  it("hides everything but the document, until Escape", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1");
    await screen.findByText("of 40");
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();

    await user.keyboard("f");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.getByRole("document", { name: "att-1.pdf" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.getByRole("navigation", { name: "Main navigation" })).toBeInTheDocument();
  });
});

describe("opening the reader at a place", () => {
  it("jumps to the passage and shows it for a moment", async () => {
    open("#/reader/att-1?anchor=a7", (backend) => {
      backend.anchors.a7 = anchorView({ id: "a7", page: 1 });
    });

    const flash = await screen.findByTestId("anchor-flash");
    // The fake page is 600 by 800 at scale 1: PDF y 620 is 180 pixels from the top.
    expect(flash).toHaveStyle({ left: "100px", top: "180px", width: "200px", height: "20px" });
    await waitFor(
      () => {
        expect(screen.queryByTestId("anchor-flash")).not.toBeInTheDocument();
      },
      { timeout: 4000 },
    );
  });

  it("does not guess when the passage is gone from the file", async () => {
    const user = userEvent.setup();
    open("#/reader/att-1?anchor=a7", (backend) => {
      backend.anchors.a7 = anchorView({ id: "a7", status: "lost", page: 30 });
    });

    const notice = await screen.findByRole("alert");
    expect(notice).toHaveTextContent("This passage is not in the current file any more:");
    expect(notice).toHaveTextContent("forty-two participants");
    expect(screen.queryByTestId("anchor-flash")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Page" })).toHaveValue("1");

    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
