import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { useSearchView } from "@/features/search/store";
import { fileToBase64 } from "@/lib/base64";
import { fakeBackend, overview, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

const RIS = "TY  - JOUR\nTI  - Automated code review with LLMs\nER  - \n";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useSearchView.setState({ activeSearchId: null, selectedPaperId: null });
  window.location.hash = "#/search";
});

function setUp() {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

async function chooseFile(user: ReturnType<typeof userEvent.setup>, name = "scopus.ris") {
  await user.click(await screen.findByRole("button", { name: "Import file" }));
  const dialog = await screen.findByRole("dialog", { name: "Import exported results" });
  const input = within(dialog).getByLabelText("Choose file");
  await user.upload(input, new File([RIS], name, { type: "application/x-research-info-systems" }));
  return dialog;
}

function lastRequest(backend: FakeBackend, path: string) {
  return backend.requests.filter((r) => r.path === path).at(-1)?.body as Record<string, unknown>;
}

describe("importing an exported file", () => {
  it("sends the file and shows what it holds, with the broken entries", async () => {
    const { backend, user } = setUp();

    const dialog = await chooseFile(user);

    expect(
      await within(dialog).findByText(
        "RIS · 3 entries · 2 readable: 1 new, 0 already found by a search, 1 in the library, 0 repeated in the file",
      ),
    ).toBeInTheDocument();
    const body = lastRequest(backend, "/imports/preview");
    expect(body.file_name).toBe("scopus.ris");
    expect(body.content_base64).toBe(await fileToBase64(new Blob([RIS])));

    const issues = within(dialog).getByRole("list", { name: "Entries that cannot be imported" });
    expect(within(issues).getByText("has no title")).toBeInTheDocument();
    expect(within(issues).getByText("line 9")).toBeInTheDocument();
    expect(within(dialog).getByText("1 without authors")).toBeInTheDocument();
    expect(within(dialog).getByText("in library")).toBeInTheDocument();
  });

  it("logs the import as a search run and opens its results", async () => {
    const { backend, user } = setUp();
    backend.searchOverview = overview({ search_id: "search-import", file_name: "scopus.ris" });
    const dialog = await chooseFile(user);
    await within(dialog).findByText(/3 entries/);

    await user.selectOptions(within(dialog).getByLabelText("Database"), "Scopus");
    const date = within(dialog).getByLabelText("Searched on");
    await user.clear(date);
    await user.type(date, "2026-11-01");
    await user.type(within(dialog).getByLabelText("Query used"), "code review");
    await user.click(within(dialog).getByRole("button", { name: "Import 2 records" }));

    expect(
      await within(dialog).findByText("2 records imported: 1 new papers, 2 added to the review."),
    ).toBeInTheDocument();
    expect(lastRequest(backend, "/imports")).toMatchObject({
      file_name: "scopus.ris",
      review_id: "review-1",
      log: { source: "Scopus", searched_at: "2026-11-01", query: "code review" },
      add_to_review: true,
      add_to_library: false,
    });

    await user.click(within(dialog).getByRole("button", { name: "Show results" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(useSearchView.getState().activeSearchId).toBe("search-import");
  });

  it("asks for a name when the database is not in the list", async () => {
    const { backend, user } = setUp();
    const dialog = await chooseFile(user);
    await within(dialog).findByText(/3 entries/);

    await user.selectOptions(within(dialog).getByLabelText("Database"), "Other…");
    const importButton = within(dialog).getByRole("button", { name: "Import 2 records" });
    expect(importButton).toBeDisabled();

    await user.type(within(dialog).getByLabelText("Database name"), "Google Scholar");
    await user.click(importButton);

    await waitFor(() => {
      expect(lastRequest(backend, "/imports")).toMatchObject({
        log: { source: "Google Scholar" },
      });
    });
  });

  it("needs at least one target", async () => {
    const { user } = setUp();
    const dialog = await chooseFile(user);
    await within(dialog).findByText(/3 entries/);

    await user.click(within(dialog).getByLabelText("Log it as a search run (history and PRISMA)"));
    await user.click(
      within(dialog).getByLabelText("Add the records to the review's screening queue"),
    );

    expect(within(dialog).getByText("Choose at least one.")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Import 2 records" })).toBeDisabled();
  });

  it("explains a file it cannot read", async () => {
    const { backend, user } = setUp();
    backend.importPreviewError = {
      code: "import.unknown_format",
      params: { file_name: "notes.txt" },
    };

    const dialog = await chooseFile(user, "notes.txt");

    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "notes.txt is neither a BibTeX nor a RIS file.",
    );
    expect(within(dialog).queryByRole("button", { name: /^Import \d/ })).toBeDisabled();
  });

  it("shows an imported run by its file name in the history", async () => {
    const { backend, user } = setUp();
    backend.searchHistory = [
      overview({ search_id: "search-import", file_name: "ieee.bib", query: "LLM review" }),
    ];

    await user.click(await screen.findByRole("radio", { name: "History" }));

    expect(await screen.findByText("Imported: ieee.bib")).toBeInTheDocument();
    expect(screen.getByText("LLM review")).toBeInTheDocument();
  });
});
