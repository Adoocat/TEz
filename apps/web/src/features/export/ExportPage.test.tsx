// Task 40: the export screen against a fake backend: scope and format choices reach the API,
// the formatted bibliography goes to the clipboard as text and HTML, BibTeX shows its keys and
// the terminal command, and the strategy table has a row per search run.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "@/api/schema";
import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import type { FetchLike } from "@/app/backend";
import type { Platform } from "@/lib/platform";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

import { useExportChoices, useExportSelection } from "./store";

type StrategyRow = components["schemas"]["StrategyRow"];

const rows: StrategyRow[] = [
  {
    run_id: "run-1",
    source: "openalex",
    method: "database",
    snowball_round: null,
    executed_at: "2026-03-01T09:00:00Z",
    query: 'title.search:("teacher" AND "burnout")',
    file_name: null,
    total_reported: 128,
    retrieved: 100,
    status: "ok",
  },
  {
    run_id: "run-2",
    source: "Scopus",
    method: "database",
    snowball_round: null,
    executed_at: "2026-03-02T10:00:00Z",
    query: 'TITLE-ABS-KEY("teacher burnout")',
    file_name: "scopus.ris",
    total_reported: null,
    retrieved: 42,
    status: "ok",
  },
  {
    run_id: "run-3",
    source: "openalex",
    method: "citation_backward",
    snowball_round: 1,
    executed_at: "2026-03-05T11:00:00Z",
    query: null,
    file_name: null,
    total_reported: null,
    retrieved: 7,
    status: "partial",
  },
];

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

/** The fake backend plus the export endpoints. */
function withExport(backend: FakeBackend): FetchLike {
  return async (request) => {
    const url = new URL(request.url, "http://test");
    if (url.pathname === "/export/bibliography") {
      const body = (await request.clone().json()) as { style: string; locale: string };
      backend.requests.push({ method: "POST", path: url.pathname, body });
      return json({
        style: body.style,
        locale: body.locale,
        count: 1,
        entries: [
          {
            citekey: "akin2020birinci",
            html: "Akın, A. (2020). Birinci. <i>Eğitim ve Bilim</i>.",
            text: "Akın, A. (2020). Birinci. Eğitim ve Bilim.",
          },
        ],
        text: "Akın, A. (2020). Birinci. Eğitim ve Bilim.",
        html: "<p>Akın, A. (2020). Birinci. <i>Eğitim ve Bilim</i>.</p>",
      });
    }
    if (url.pathname === "/export/references") {
      const body = (await request.clone().json()) as { format: string };
      backend.requests.push({ method: "POST", path: url.pathname, body });
      return json({
        format: body.format,
        count: 1,
        content: "@article{akin2020birinci,\n  title = {{Birinci}}\n}\n",
        citekeys: ["akin2020birinci"],
      });
    }
    if (url.pathname === "/export/search-strategy") return json({ review_id: "review-1", rows });
    return backend.fetch(request);
  };
}

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: "review-1" });
  useExportChoices.setState({ format: "bibliography", style: "apa", locale: null });
  useExportSelection.setState({ paperIds: [] });
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

function open(platform: Platform = readyPlatform) {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review({ id: "review-1", title: "Teacher burnout SLR" }));
  window.location.hash = "#/export";
  render(<App platform={platform} fetch={withExport(backend)} />);
  return backend;
}

function lastBody(backend: FakeBackend, path: string): unknown {
  return backend.requests.filter((r) => r.path === path).at(-1)?.body;
}

describe("the export screen", () => {
  it("copies the included studies' APA bibliography as text and HTML", async () => {
    const copyText = vi.fn(() => Promise.resolve());
    const backend = open({ ...readyPlatform, copyText });
    const user = userEvent.setup();

    const preview = await screen.findByRole("list", { name: "Preview" });
    expect((await within(preview).findByText("Eğitim ve Bilim")).tagName).toBe("I");
    expect(lastBody(backend, "/export/bibliography")).toEqual({
      style: "apa",
      locale: "en-US",
      review_id: "review-1",
    });

    await user.click(screen.getByRole("button", { name: "Copy to clipboard" }));

    expect(copyText).toHaveBeenCalledWith(
      "Akın, A. (2020). Birinci. Eğitim ve Bilim.",
      "<p>Akın, A. (2020). Birinci. <i>Eğitim ve Bilim</i>.</p>",
    );
    expect(await screen.findByText("Copied to the clipboard.")).toBeInTheDocument();
  });

  it("asks for the chosen style and language", async () => {
    const backend = open();
    const user = userEvent.setup();
    await screen.findByRole("list", { name: "Preview" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Style" }), "vancouver");
    await user.click(screen.getByRole("radio", { name: "Türkçe" }));

    await waitFor(() => {
      expect(lastBody(backend, "/export/bibliography")).toMatchObject({
        style: "vancouver",
        locale: "tr-TR",
      });
    });
  });

  it("shows BibTeX keys and the terminal command, and saves the file", async () => {
    const saveFile = vi.fn(() => Promise.resolve());
    const copyText = vi.fn(() => Promise.resolve());
    const backend = open({ ...readyPlatform, saveFile, copyText });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: "BibTeX" }));

    expect(await screen.findByText("akin2020birinci")).toBeInTheDocument();
    expect(lastBody(backend, "/export/references")).toEqual({
      format: "bibtex",
      review_id: "review-1",
      included: true,
    });
    expect(
      screen.getByText(
        'tez export --format bibtex --review "Teacher burnout SLR" --included --output references.bib',
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save to file (references.bib)" }));
    expect(saveFile).toHaveBeenCalledWith(
      "references.bib",
      "@article{akin2020birinci,\n  title = {{Birinci}}\n}\n",
      "application/x-bibtex",
    );
    await user.click(screen.getByRole("button", { name: "Copy terminal command" }));
    expect(copyText).toHaveBeenLastCalledWith(
      'tez export --format bibtex --review "Teacher burnout SLR" --included --output references.bib',
    );
  });

  it("offers papers chosen in the library, with no terminal command", async () => {
    useExportSelection.setState({ paperIds: ["p1", "p2"] });
    useExportChoices.setState({ format: "ris" });
    const backend = open();

    expect(await screen.findByRole("radio", { name: /Selected papers \(2\)/ })).toBeChecked();
    await waitFor(() => {
      expect(lastBody(backend, "/export/references")).toEqual({
        format: "ris",
        paper_ids: ["p1", "p2"],
        included: false,
      });
    });
    expect(screen.getByText("There is no terminal command for selected papers.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Copy terminal command" })).toBeDisabled();
  });

  it("lists every search run and copies the table as Markdown", async () => {
    const copyText = vi.fn(() => Promise.resolve());
    open({ ...readyPlatform, copyText });
    const user = userEvent.setup();

    const table = await screen.findByRole("table");
    await waitFor(() => {
      expect(within(table).getAllByRole("row")).toHaveLength(1 + rows.length);
    });
    expect(within(table).getByText("Scopus (scopus.ris)")).toBeInTheDocument();
    expect(within(table).getByText("Backward snowballing, round 1")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Copy Markdown" }));

    const markdown = (copyText.mock.calls[0] as unknown as [string])[0];
    expect(markdown.split("\n")).toHaveLength(2 + rows.length);
    expect(markdown).toContain("| 2 | Scopus (scopus.ris) | Database search | 2026-03-02 |");
  });
});
