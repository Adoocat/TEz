import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import type { PdfDocument } from "@/lib/pdf";
import {
  anchorView,
  annotationView,
  fakeBackend,
  noteView,
  readyPlatform,
} from "@/test/fakeBackend";

import { useReaderSelection, useReaderTabs, useReadingPanel } from "./store";

vi.mock("@/lib/pdf", () => ({
  openPdf: (): Promise<PdfDocument> => Promise.reject(new Error("not drawn in this test")),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true, focus: false });
  useReaderTabs.setState({ tabs: [], activeId: null });
  useReadingPanel.setState({ tab: "highlights" });
  useReaderSelection.setState({ selectedId: null, editing: false, color: "yellow" });
});

function open() {
  window.location.hash = "#/reader/att-1";
  const backend = fakeBackend({ language: "en" });
  backend.annotations["att-1"] = [
    annotationView({
      id: "one",
      comment: "check this",
      anchor: anchorView({ id: "a1", page: 4, quote: "forty-two participants" }),
    }),
    annotationView({
      id: "two",
      color: "green",
      anchor: anchorView({
        id: "a2",
        page: 9,
        quote: "I\u015f\u0131k h\u0131z\u0131",
        status: "lost",
      }),
    }),
    annotationView({
      id: "three",
      kind: "area",
      anchor: anchorView({ id: "a3", page: 12, kind: "area", quote: "" }),
    }),
  ];
  const user = userEvent.setup();
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user };
}

async function panel() {
  return screen.findByRole("region", { name: "Highlights (3)" });
}

describe("the highlights panel", () => {
  it("lists highlights with their page; a page chip opens that place", async () => {
    open();

    const items = within(await panel()).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    const [first, second, third] = items as [HTMLElement, HTMLElement, HTMLElement];
    expect(within(first).getByRole("link", { name: "p. 4" })).toHaveAttribute(
      "href",
      "#/reader/att-1?anchor=a1",
    );
    expect(within(second).getByText("Not in the current file any more")).toBeInTheDocument();
    expect(within(third).getByLabelText("Marked area")).toBeInTheDocument();
  });

  it("searches quotes and comments, Turkish letters folded", async () => {
    const { user } = open();
    const box = within(await panel()).getByRole("searchbox", { name: "Search highlights" });

    await user.type(box, "ISIK");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await user.clear(box);
    await user.type(box, "check");
    expect(screen.getByText("forty-two participants")).toBeInTheDocument();
    await user.clear(box);
    await user.type(box, "zzz");
    expect(screen.getByText("No highlight matches.")).toBeInTheDocument();
  });

  it("saves a comment when the field is left, and changes the colour", async () => {
    const { backend, user } = open();
    const [first] = within(await panel()).getAllByRole("listitem");
    if (!first) throw new Error("no highlight");
    const field = within(first).getByRole("textbox", { name: "Comment" });

    await user.clear(field);
    await user.type(field, "read again");
    await user.tab();
    await user.click(within(first).getByRole("button", { name: "Highlight in pink" }));

    await waitFor(() => {
      expect(
        backend.requests.filter((r) => r.path === "/annotations/one").map((r) => r.body),
      ).toEqual([{ comment: "read again" }, { color: "pink" }]);
    });
  });

  it("deletes a highlight and brings it back", async () => {
    const { backend, user } = open();
    const [first] = within(await panel()).getAllByRole("listitem");
    if (!first) throw new Error("no highlight");

    await user.click(within(first).getByRole("button", { name: "Delete the highlight" }));
    expect(await screen.findByText("Highlight deleted.")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("forty-two participants")).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("forty-two participants")).toBeInTheDocument();
    const restored = backend.annotations["att-1"]?.at(-1);
    expect([restored?.comment, restored?.anchor.page]).toEqual(["check this", 4]);
  });
});

describe("from a highlight to a note", () => {
  it("offers notes about the paper first, and adds the quote with its chip", async () => {
    const { backend, user } = open();
    backend.notes = [
      noteView({ id: "n1", title: "Something else" }),
      noteView({ id: "n2", title: "Reading Lovelace", body: "Start." }),
    ];
    backend.backlinks["paper-1"] = [{ note_id: "n2", title: "Reading Lovelace", passage: "" }];
    const [first] = within(await panel()).getAllByRole("listitem");
    if (!first) throw new Error("no highlight");

    await user.click(within(first).getByRole("button", { name: "Quote in a note" }));
    const dialog = await screen.findByRole("dialog", { name: "Quote in a note" });
    const choices = within(dialog).getByRole("list", { name: "Notes" });
    await within(choices).findByText("about this paper");
    expect(
      within(choices)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["New note about this paper", "Reading Lovelaceabout this paper", "Something else"]);
    await user.click(within(choices).getByRole("button", { name: /Reading Lovelace/ }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(backend.notes[1]?.body).toBe(
      "Start.\n\n> forty-two participants\n>\n> [Lovelace et al. 2024, p. 4](tez:anchor/a1)",
    );
  });

  it("starts a new note about the paper", async () => {
    const { backend, user } = open();
    const [first] = within(await panel()).getAllByRole("listitem");
    if (!first) throw new Error("no highlight");
    await user.click(within(first).getByRole("button", { name: "Quote in a note" }));
    await user.click(await screen.findByRole("button", { name: "New note about this paper" }));

    await waitFor(() => {
      expect(backend.notes).toHaveLength(1);
    });
    expect(backend.notes[0]).toMatchObject({ title: "First paper", paper_id: "paper-1" });
  });

  it("lists the notes about the paper in its own tab", async () => {
    const { backend, user } = open();
    backend.backlinks["paper-1"] = [
      { note_id: "n2", title: "Reading Lovelace", passage: "as she says" },
    ];
    await panel();
    await user.click(screen.getByRole("radio", { name: "Notes" }));

    const notes = await screen.findByRole("region", { name: "Notes about this paper" });
    expect(await within(notes).findByRole("link", { name: "Reading Lovelace" })).toHaveAttribute(
      "href",
      "#/notes/n2",
    );
    expect(within(notes).getByText("as she says")).toBeInTheDocument();
  });
});
