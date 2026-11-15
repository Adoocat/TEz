import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { useSearchView } from "@/features/search/store";
import type { Platform } from "@/lib/platform";
import {
  externalSearch,
  fakeBackend,
  importOutcome,
  importPreview,
  readyPlatform,
  review,
  type FakeBackend,
} from "@/test/fakeBackend";

const RIS = "TY  - JOUR\nTI  - Automated code review with LLMs\nER  - \n";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useSearchView.setState({ activeSearchId: null, selectedPaperId: null });
  window.location.hash = "#/search";
});

function setUp(platform: Platform = readyPlatform) {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  const user = userEvent.setup();
  render(<App platform={platform} fetch={backend.fetch} />);
  return { backend, user };
}

async function openTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("radio", { name: "External databases" }));
}

function lastRequest(backend: FakeBackend, path: string) {
  return backend.requests.filter((r) => r.method !== "GET" && r.path === path).at(-1)
    ?.body as Record<string, unknown>;
}

describe("saved external searches", () => {
  it("shows how to export from the chosen database", async () => {
    const { user } = setUp();
    await openTab(user);

    expect(await screen.findByText(/RIS \(other reference software\)/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Database"), "Google Scholar");
    expect(screen.getByText(/Import into BibTeX/)).toBeInTheDocument();
  });

  it("logs an import under a tested database preset", async () => {
    const { backend, user } = setUp();
    backend.presets = [{ key: "jstor", name: "JSTOR", formats: ["ris"] }];
    await user.click(await screen.findByRole("button", { name: "Import file" }));
    const dialog = await screen.findByRole("dialog", { name: "Import exported results" });
    await user.upload(
      within(dialog).getByLabelText("Choose file"),
      new File([RIS], "jstor.ris", { type: "application/x-research-info-systems" }),
    );
    await user.selectOptions(await within(dialog).findByLabelText("Database"), "JSTOR");
    await user.click(within(dialog).getByRole("button", { name: /^Import \d/ }));

    await within(dialog).findByRole("status");
    expect(lastRequest(backend, "/imports").log).toMatchObject({ preset: "jstor" });
    expect(lastRequest(backend, "/imports").log).not.toHaveProperty("source");
  });

  it("saves a database and its query, and lists it", async () => {
    const { backend, user } = setUp();
    await openTab(user);

    expect(await screen.findByText(/No saved external search yet/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Database"), "Web of Science");
    await user.type(screen.getByLabelText("Query run on the site"), 'TS=("öğretmen")');
    await user.click(screen.getByRole("button", { name: "Save search" }));

    const list = await screen.findByRole("list", { name: "Saved external searches" });
    expect(lastRequest(backend, "/searches/external")).toEqual({
      review_id: "review-1",
      source: "Web of Science",
      query: 'TS=("öğretmen")',
      name: null,
    });
    expect(within(list).getByText('TS=("öğretmen")')).toBeInTheDocument();
    expect(within(list).getByText("Not imported yet")).toBeInTheDocument();
  });

  it("opens the site in the browser and copies the query", async () => {
    const openExternal = vi.fn(() => Promise.resolve());
    const { backend, user } = setUp({ ...readyPlatform, openExternal });
    backend.externalSearches = [externalSearch()];
    await openTab(user);

    await user.click(await screen.findByRole("button", { name: "Open site" }));

    expect(openExternal).toHaveBeenCalledWith("https://www.scopus.com/search/form.uri");
    expect(await navigator.clipboard.readText()).toBe('TITLE-ABS-KEY("code review")');
    expect(await screen.findByText("Query copied. Paste it on the site.")).toBeInTheDocument();
  });

  it("only copies the query of a database it has no address for", async () => {
    const openExternal = vi.fn(() => Promise.resolve());
    const { backend, user } = setUp({ ...readyPlatform, openExternal });
    backend.externalSearches = [externalSearch({ source: "Our Faculty Repository" })];
    await openTab(user);

    expect(screen.queryByRole("button", { name: "Open site" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Copy query" }));

    expect(openExternal).not.toHaveBeenCalled();
    expect(await navigator.clipboard.readText()).toBe('TITLE-ABS-KEY("code review")');
  });

  it("imports a new export of the search and says what is new since the last one", async () => {
    const { backend, user } = setUp();
    backend.externalSearches = [
      externalSearch({
        imports: 1,
        last_searched_at: "2026-10-12T00:00:00Z",
        last_retrieved: 412,
      }),
    ];
    backend.importPreview = importPreview({
      since_last: { last_searched_at: "2026-10-12T00:00:00Z", new: 7 },
    });
    backend.importOutcome = importOutcome({
      since_last: { last_searched_at: "2026-10-12T00:00:00Z", new: 7 },
      added_to_review: 7,
    });
    await openTab(user);
    expect(await screen.findByText(/1 import · last searched Oct 12, 2026 · 412 records/));

    await user.click(screen.getByRole("button", { name: "Import new export" }));
    const dialog = await screen.findByRole("dialog", { name: "Import exported results" });
    await user.upload(
      within(dialog).getByLabelText("Choose file"),
      new File([RIS], "scopus.ris", { type: "application/x-research-info-systems" }),
    );

    expect(
      await within(dialog).findByText("7 new records since the last import (Oct 12, 2026)"),
    ).toBeInTheDocument();
    expect(lastRequest(backend, "/imports/preview")).toMatchObject({
      saved_search_id: "external-1",
    });
    expect(within(dialog).getByLabelText("Saved external search")).toHaveValue("external-1");
    expect(within(dialog).queryByLabelText("Query used")).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Import 2 records" }));

    expect(await within(dialog).findByRole("status")).toHaveTextContent(
      "7 new records since the last import (Oct 12, 2026)",
    );
    const sent = lastRequest(backend, "/imports");
    expect(sent.log).toMatchObject({ saved_search_id: "external-1" });
    expect(sent.log).not.toHaveProperty("source");
  });
});
