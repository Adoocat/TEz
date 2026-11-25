import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import type { PdfDocument } from "@/lib/pdf";
import { anchorView, annotationView, fakeBackend, readyPlatform } from "@/test/fakeBackend";

import { useReaderSelection, useReaderTabs } from "./store";

vi.mock("@/lib/pdf", () => ({
  openPdf: (): Promise<PdfDocument> => Promise.reject(new Error("not drawn in this test")),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true, focus: false });
  useReaderTabs.setState({ tabs: [], activeId: null });
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
