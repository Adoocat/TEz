import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, libraryPaper, readyPlatform, type FakeBackend } from "@/test/fakeBackend";

import { COLLECTION_TYPE, PAPERS_TYPE } from "./dnd";
import { useLibraryView } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useLibraryView.setState({ scope: { kind: "all" }, selectedPaperId: null });
  window.location.hash = "#/library";
  // jsdom has no layout; the virtualized table needs a size to decide which rows to draw.
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(900);
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

function withLibrary() {
  const backend = fakeBackend({ language: "en" });
  backend.collections = [
    {
      id: "inbox",
      parent_id: null,
      name: "inbox",
      sort_order: -1,
      is_system: true,
      paper_count: 1,
    },
    {
      id: "thesis",
      parent_id: null,
      name: "Thesis",
      sort_order: 0,
      is_system: false,
      paper_count: 1,
    },
    {
      id: "method",
      parent_id: "thesis",
      name: "Method",
      sort_order: 0,
      is_system: false,
      paper_count: 0,
    },
  ];
  backend.tags = [{ id: "survey", name: "survey", color: "blue", paper_count: 1 }];
  backend.papers = [
    libraryPaper({
      id: "p1",
      title: "First paper",
      collection_ids: ["thesis"],
      tag_ids: ["survey"],
    }),
    libraryPaper({
      id: "p2",
      title: "Second paper",
      collection_ids: ["inbox"],
      reading_status: "read",
    }),
  ];
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

function sidebar() {
  return screen.getByRole("navigation", { name: "Library" });
}

/** The writes sent to a path (reads of the same path are left out). */
function requestsTo(backend: FakeBackend, path: string) {
  return backend.requests.filter((r) => r.path === path && r.method !== "GET");
}

/** jsdom has no DataTransfer; this carries what our drag handlers read and write. */
function transfer(data: Record<string, string>) {
  return {
    types: Object.keys(data),
    getData: (type: string) => data[type] ?? "",
    setData: (type: string, value: string) => {
      data[type] = value;
    },
    effectAllowed: "all",
  };
}

describe("the library sidebar", () => {
  it("shows the inbox, all papers, the collection tree and tags with counts", async () => {
    withLibrary();

    expect(
      await within(await screen.findByRole("navigation", { name: "Library" })).findByText("Inbox"),
    ).toBeInTheDocument();
    const nav = sidebar();
    expect(within(nav).getByRole("button", { name: "All papers" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Thesis" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Method" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "#survey" })).toBeInTheDocument();
    await waitFor(() => {
      expect(within(nav).getAllByText("2")).toHaveLength(1); // all papers
    });
  });

  it("narrows the list to a collection or a tag", async () => {
    const { user } = withLibrary();
    await screen.findByText("Second paper");

    await user.click(within(sidebar()).getByRole("button", { name: "Thesis" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Thesis" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Second paper")).not.toBeInTheDocument();
    });
    expect(screen.getByText("First paper")).toBeInTheDocument();

    await user.click(within(sidebar()).getByRole("button", { name: "Inbox" }));
    expect(await screen.findByText("Second paper")).toBeInTheDocument();
  });

  it("creates a collection and a sub-collection", async () => {
    const { backend, user } = withLibrary();
    await screen.findByText("First paper");

    await user.click(within(sidebar()).getByRole("button", { name: "New collection" }));
    await user.type(
      screen.getByRole("textbox", { name: "Collection name" }),
      "Related work{Enter}",
    );
    await user.click(
      within(sidebar()).getByRole("button", { name: "New collection inside Thesis" }),
    );
    await user.type(screen.getByRole("textbox", { name: "Collection name" }), "Results{Enter}");

    await waitFor(() => {
      expect(requestsTo(backend, "/collections").map((r) => r.body)).toEqual([
        { name: "Related work", parent_id: null },
        { name: "Results", parent_id: "thesis" },
      ]);
    });
    expect(await within(sidebar()).findByRole("button", { name: "Results" })).toBeInTheDocument();
  });

  it("renames and deletes a collection after asking", async () => {
    const { backend, user } = withLibrary();
    await screen.findByText("First paper");

    await user.click(within(sidebar()).getByRole("button", { name: "Rename Method" }));
    const field = screen.getByRole("textbox", { name: "New name" });
    await user.clear(field);
    await user.type(field, "Methods{Enter}");
    await waitFor(() => {
      expect(requestsTo(backend, "/collections/method")[0]?.body).toEqual({ name: "Methods" });
    });

    await user.click(within(sidebar()).getByRole("button", { name: "Delete Thesis" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete “Thesis”?" });
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(
        backend.requests.some((r) => r.method === "DELETE" && r.path === "/collections/thesis"),
      ).toBe(true);
    });
  });

  it("files papers dropped on a collection and tags papers dropped on a tag", async () => {
    const { backend } = withLibrary();
    await screen.findByText("First paper");
    const ids = JSON.stringify(["p1", "p2"]);

    const method = within(sidebar()).getByRole("button", { name: "Method" }).parentElement;
    fireEvent.dragOver(method as Element, { dataTransfer: transfer({ [PAPERS_TYPE]: ids }) });
    fireEvent.drop(method as Element, { dataTransfer: transfer({ [PAPERS_TYPE]: ids }) });
    const tag = within(sidebar()).getByRole("button", { name: "#survey" }).parentElement;
    fireEvent.drop(tag as Element, { dataTransfer: transfer({ [PAPERS_TYPE]: ids }) });

    await waitFor(() => {
      expect(requestsTo(backend, "/collections/method/papers")[0]?.body).toEqual({
        paper_ids: ["p1", "p2"],
      });
      expect(requestsTo(backend, "/tags/survey/papers")[0]?.body).toEqual({
        paper_ids: ["p1", "p2"],
      });
    });
  });

  it("moves a collection dropped on another, or on the heading to the top", async () => {
    const { backend } = withLibrary();
    await screen.findByText("First paper");

    const thesis = within(sidebar()).getByRole("button", { name: "Thesis" }).parentElement;
    fireEvent.drop(thesis as Element, { dataTransfer: transfer({ [COLLECTION_TYPE]: "other" }) });
    const heading = within(sidebar()).getByRole("heading", { name: "Collections" }).parentElement;
    fireEvent.drop(heading as Element, { dataTransfer: transfer({ [COLLECTION_TYPE]: "method" }) });

    await waitFor(() => {
      expect(requestsTo(backend, "/collections/other")[0]?.body).toEqual({ parent_id: "thesis" });
      expect(requestsTo(backend, "/collections/method")[0]?.body).toEqual({ parent_id: null });
    });
  });

  it("creates a tag with the next colour", async () => {
    const { backend, user } = withLibrary();
    await screen.findByText("First paper");

    await user.click(within(sidebar()).getByRole("button", { name: "New tag" }));
    await user.type(screen.getByRole("textbox", { name: "Tag name" }), "#benchmark{Enter}");

    await waitFor(() => {
      expect(requestsTo(backend, "/tags")[0]?.body).toEqual({ name: "benchmark", color: "green" });
    });
  });
});

describe("the paper list", () => {
  it("drags the selected rows together", async () => {
    withLibrary();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("checkbox", { name: "Select: First paper" }));
    await user.click(screen.getByRole("checkbox", { name: "Select: Second paper" }));

    const data: Record<string, string> = {};
    const row = screen.getByText("First paper").closest('[role="row"]');
    expect(row).not.toBeNull();
    fireEvent.dragStart(row ?? document.body, { dataTransfer: transfer(data) });

    expect(JSON.parse(data[PAPERS_TYPE] ?? "[]")).toEqual(["p1", "p2"]);
  });

  it("sets reading status and tags for a selection", async () => {
    const { backend, user } = withLibrary();
    await user.click(await screen.findByRole("checkbox", { name: "Select all" }));

    await user.selectOptions(screen.getByRole("combobox", { name: "Reading status…" }), "Reading");
    await user.selectOptions(screen.getByRole("combobox", { name: "Add tag…" }), "#survey");

    await waitFor(() => {
      expect(requestsTo(backend, "/papers/reading-status")[0]?.body).toEqual({
        paper_ids: ["p1", "p2"],
        reading_status: "reading",
      });
      expect(requestsTo(backend, "/tags/survey/papers")[0]?.body).toEqual({
        paper_ids: ["p1", "p2"],
      });
    });
    expect(screen.getByRole("img", { name: "Read" })).toBeInTheDocument();
  });

  it("removes papers from the collection being shown", async () => {
    const { backend, user } = withLibrary();
    await user.click(await within(sidebar()).findByRole("button", { name: "Thesis" }));
    await user.click(await screen.findByRole("checkbox", { name: "Select: First paper" }));

    await user.click(screen.getByRole("button", { name: "Remove from this collection" }));

    await waitFor(() => {
      expect(requestsTo(backend, "/collections/thesis/papers/remove")[0]?.body).toEqual({
        paper_ids: ["p1"],
      });
    });
  });

  it("says what to do when the library is empty", async () => {
    const backend = fakeBackend({ language: "en" });
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    expect(
      await screen.findByText(
        "The library is empty. Add papers from a search, import a file, or drop PDFs here.",
      ),
    ).toBeInTheDocument();
  });
});
