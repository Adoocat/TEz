// pdf.js does not run in jsdom: these tests stand in a fake document and check the reader's
// own behaviour. Real rendering, ranges and memory are checked by e2e/reader.spec.ts.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import type { OpenOptions, PdfDocument } from "@/lib/pdf";
import { fakeBackend, readyPlatform } from "@/test/fakeBackend";

const opened: OpenOptions[] = [];
const rendered: { page: number; scale: number }[] = [];
let failOpen = false;

vi.mock("@/lib/pdf", () => ({
  openPdf: (options: OpenOptions): Promise<PdfDocument> => {
    opened.push(options);
    if (failOpen) return Promise.reject(new Error("broken"));
    return Promise.resolve({
      numPages: 40,
      pageSize: () => Promise.resolve({ width: 600, height: 800 }),
      renderPage: (page, { scale }) => {
        rendered.push({ page, scale });
        return { done: Promise.resolve(), dispose: () => undefined };
      },
      destroy: () => Promise.resolve(),
    });
  },
}));

beforeEach(() => {
  opened.length = 0;
  rendered.length = 0;
  failOpen = false;
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

function open(hash: string) {
  window.location.hash = hash;
  const backend = fakeBackend({ language: "en" });
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
