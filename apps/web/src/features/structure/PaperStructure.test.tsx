// Task 56: GROBID is optional. Without an address its tab is not there; with one, the reading
// panel reads a paper's sections and references on request.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useReaderTabs, useReadingPanel } from "@/features/reader/store";
import type { PdfDocument } from "@/lib/pdf";
import { fakeBackend, readyPlatform, type FakeBackend } from "@/test/fakeBackend";

vi.mock("@/lib/pdf", () => ({
  openPdf: (): Promise<PdfDocument> => Promise.reject(new Error("not drawn in this test")),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: false, inspectorOpen: true, focus: false });
  useReaderTabs.setState({ tabs: [], activeId: null });
  useReadingPanel.setState({ tab: "highlights" });
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

function open(hash: string, prepare?: (backend: FakeBackend) => void) {
  window.location.hash = hash;
  const backend = fakeBackend({ language: "en" });
  prepare?.(backend);
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

const READ = {
  read_at: "2026-11-27T10:00:00Z",
  error: null,
  sections: [
    { type: "intro", heading: "1. Giriş", page_start: 1, page_end: 2 },
    { type: "method", heading: "2. Yöntem", page_start: 2, page_end: 4 },
    { type: "other", heading: "Teşekkür", page_start: null, page_end: null },
  ],
  references: [
    {
      ord: 0,
      raw_text: "Yılmaz, A. (2019). White storks.",
      title: "White storks",
      authors: ["Ayşe Yılmaz"],
      year: 2019,
      doi: null,
      page: 6,
      matched_paper_id: "paper-9",
    },
    {
      ord: 1,
      raw_text: "Kaya, M. (2008). Kuşların göçü.",
      title: "Kuşların göçü",
      authors: [],
      year: 2008,
      doi: null,
      page: 6,
      matched_paper_id: null,
    },
  ],
};

describe("GROBID", () => {
  it("has no tab while no address is set", async () => {
    open("#/reader/att-1");
    const tabs = await screen.findByRole("radiogroup", { name: "Reading panel" });
    expect(
      within(tabs)
        .getAllByRole("radio")
        .map((r) => r.textContent),
    ).toEqual(["Highlights", "Notes", "Matrix"]);
  });

  it("reads sections and references on request", async () => {
    const { user } = open("#/reader/att-1", (backend) => {
      backend.settings.grobid_url = "http://localhost:8070";
      backend.structureNext = READ;
    });
    await user.click(await screen.findByRole("radio", { name: "Structure" }));
    expect(await screen.findByText("GROBID has not read this paper yet.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Read sections and references (GROBID)" }));

    const sections = await screen.findByRole("region", { name: "Sections" });
    expect(within(sections).getByRole("link", { name: /1\. Giriş/ })).toHaveAttribute(
      "href",
      "#/reader/att-1?page=1",
    );
    expect(within(sections).getByRole("link", { name: /2\. Yöntem/ })).toHaveTextContent(
      "Method · p. 2",
    );
    expect(within(sections).queryByRole("link", { name: /Teşekkür/ })).not.toBeInTheDocument();
    const references = screen.getByRole("region", { name: "2 references" });
    const [first, second] = within(references).getAllByRole("listitem");
    expect(first).toHaveTextContent("in your library");
    expect(second).not.toHaveTextContent("in your library");
    expect(screen.getByRole("button", { name: "Read again" })).toBeEnabled();
  });

  it("says why a reading failed", async () => {
    const { user } = open("#/reader/att-1", (backend) => {
      backend.settings.grobid_url = "http://localhost:8070";
      backend.structures["att-1"] = { ...READ, read_at: null, error: "grobid.unreachable" };
    });
    await user.click(await screen.findByRole("radio", { name: "Structure" }));
    const said = await screen.findByText(/GROBID does not answer at the address in Settings/);
    expect(said).toHaveAttribute("role", "alert");
  });

  it("takes only an address on this computer in the settings", async () => {
    const { backend, user } = open("#/settings/sources");
    const field = await screen.findByRole("textbox", { name: "GROBID address (optional)" });
    await user.type(field, "http://lab.example.edu:8070");
    expect(screen.getByText(/Only an address on this computer/)).toBeInTheDocument();
    expect(field.closest("form")?.querySelector("button")).toBeDisabled();
    await user.clear(field);
    await user.type(field, "http://localhost:8070{Enter}");
    await waitFor(() => {
      expect(backend.settings.grobid_url).toBe("http://localhost:8070");
    });
  });
});
