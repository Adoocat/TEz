// Task 22: what TEz does with `tez <file>`, "Open with TEz" and `tez://` links. The same
// requests reach a window that has just started and one that was already open; both must
// end the same way.
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useUploadStore } from "@/features/files/store";
import { useJobsStore } from "@/features/jobs/store";
import { useLibraryView } from "@/features/library/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import type { OpenRequest, Platform } from "@/lib/platform";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

import { useOpenStore } from "./store";
import { routeOf } from "./useOpenRequests";

vi.mock("@/lib/pdf", () => ({
  openPdf: () =>
    Promise.resolve({
      numPages: 3,
      pageSize: () => Promise.resolve({ width: 600, height: 800 }),
      renderPage: () => ({ done: Promise.resolve(), dispose: () => undefined }),
      destroy: () => Promise.resolve(),
    }),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useUploadStore.setState({ notices: [] });
  useOpenStore.setState({ importPath: null });
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

/** A desktop-like platform: requests waiting at start-up, and a way to send more later. */
function desktop(atStart: OpenRequest[]) {
  let handler: ((requests: OpenRequest[]) => void) | null = null;
  const platform: Platform = {
    ...readyPlatform,
    kind: "tauri",
    onOpenRequests(handle) {
      handler = handle;
      if (atStart.length > 0) handle(atStart);
      return () => {
        handler = null;
      };
    },
  };
  return {
    platform,
    send(requests: OpenRequest[]) {
      act(() => {
        handler?.(requests);
      });
    },
  };
}

function start(atStart: OpenRequest[] = []) {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  const shell = desktop(atStart);
  render(<App platform={shell.platform} fetch={backend.fetch} />);
  return { backend, send: shell.send.bind(shell) };
}

function fromPaths(backend: FakeBackend) {
  return backend.requests.filter((r) => r.path === "/pdfs/from-paths").map((r) => r.body);
}

const PDF: OpenRequest = { kind: "pdf", path: "C:/papers/Kim 2024.pdf" };

describe("a PDF opened from outside", () => {
  it("goes to the inbox and opens in the reader when the app starts with it", async () => {
    const { backend } = start([PDF]);

    expect(await screen.findByText("Added to the inbox.")).toBeInTheDocument();
    expect(fromPaths(backend)).toEqual([{ paths: ["C:/papers/Kim 2024.pdf"] }]);
    await waitFor(() => {
      expect(window.location.hash).toBe("#/reader/att-0");
    });
  });

  it("ends the same way when the app was already open", async () => {
    const { backend, send } = start();
    await screen.findByRole("heading", { level: 1, name: "All papers" });

    send([PDF]);

    expect(await screen.findByText("Added to the inbox.")).toBeInTheDocument();
    expect(fromPaths(backend)).toEqual([{ paths: ["C:/papers/Kim 2024.pdf"] }]);
    await waitFor(() => {
      expect(window.location.hash).toBe("#/reader/att-0");
    });
  });

  it("is opened, not copied, when it is already in the library", async () => {
    start([{ kind: "pdf", path: "C:/papers/dup.pdf" }]);

    expect(
      await screen.findByText("Already in the library: nothing was copied."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(window.location.hash).toBe("#/reader/att-0");
    });
  });
});

describe("several PDFs or a folder", () => {
  it("go to the inbox with one summary", async () => {
    const { backend } = start([
      {
        kind: "folder",
        path: "C:/papers",
        is_library: false,
        pdfs: ["C:/papers/a.pdf", "C:/papers/dup.pdf", "C:/papers/bad.pdf"],
        truncated: false,
      },
    ]);

    expect(
      await screen.findByText(
        "1 added to the inbox · 1 already in the library · 1 could not be added",
      ),
    ).toBeInTheDocument();
    expect(fromPaths(backend)).toHaveLength(1);
    expect(window.location.hash).toBe("#/library");
  });

  it("say so for a library folder, an empty folder, a missing or unknown file", async () => {
    start([
      { kind: "folder", path: "C:/TEz Library", is_library: true, pdfs: [], truncated: false },
      { kind: "folder", path: "C:/empty", is_library: false, pdfs: [], truncated: false },
      { kind: "missing", path: "C:/gone.pdf" },
      { kind: "unsupported", path: "C:/notes.txt" },
    ]);

    expect(await screen.findByText(/This folder is a TEz library/)).toBeInTheDocument();
    expect(screen.getByText("No PDFs in this folder.")).toBeInTheDocument();
    expect(screen.getByText("File not found.")).toBeInTheDocument();
    expect(screen.getByText("TEz opens PDF, BibTeX and RIS files.")).toBeInTheDocument();
  });
});

describe("a BibTeX or RIS file", () => {
  it("opens the import dialog, read by the backend from its path", async () => {
    const { backend } = start([{ kind: "import", path: "C:/exports/ieee.bib" }]);

    expect(
      await screen.findByRole("dialog", { name: "Import exported results" }),
    ).toBeInTheDocument();
    expect(screen.getByText("ieee.bib")).toBeInTheDocument();
    await waitFor(() => {
      expect(backend.requests.find((r) => r.path === "/imports/preview")?.body).toEqual({
        file_name: "ieee.bib",
        path: "C:/exports/ieee.bib",
      });
    });
  });
});

describe("tez:// links", () => {
  it("only navigate", async () => {
    const { send, backend } = start();
    await screen.findByRole("heading", { level: 1, name: "All papers" });

    send([{ kind: "link", url: "tez://reader/att-9?page=4" }]);
    await waitFor(() => {
      expect(window.location.hash).toBe("#/reader/att-9?page=4");
    });

    send([{ kind: "link", url: "tez://delete/everything" }]);
    expect(await screen.findByText("TEz does not know this link.")).toBeInTheDocument();
    expect(backend.requests.every((r) => r.method === "GET" || r.path !== "/papers")).toBe(true);
  });

  it("map to app routes", () => {
    expect(routeOf("tez://reader/abc?page=12")).toEqual({ route: "/reader/abc?page=12" });
    expect(routeOf("tez://reader")).toEqual({ route: "/reader" });
    expect(routeOf("tez://paper/p1")).toEqual({ route: "/library", paperId: "p1" });
    expect(routeOf("tez://library")).toEqual({ route: "/library" });
    expect(routeOf("tez://import/C:/x.bib")).toBeNull();
    expect(routeOf("https://example.org")).toBeNull();
    expect(routeOf("not a url")).toBeNull();
  });
});
