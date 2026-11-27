// Task 55: the gallery of kept figures and tables. Filtering, the way back to the PDF,
// comparing, editing and deleting. The reader side is in e2e/gallery.spec.ts.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { assetView, fakeBackend, readyPlatform } from "@/test/fakeBackend";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: false, inspectorOpen: false });
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:picture" }));
  // Radix measures its radio items; jsdom has no ResizeObserver.
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

function setUp() {
  window.location.hash = "#/gallery";
  const backend = fakeBackend({ language: "en" });
  backend.assets = [
    assetView({ id: "a1", label: "Figure 2", caption: "Nest density" }),
    assetView({ id: "a2", kind: "table", label: "Table 1", caption: "Sites", page: 5 }),
    assetView({ id: "a3", label: "", caption: "" }),
  ];
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return { backend, user: userEvent.setup() };
}

/** The gallery, once its items are there. */
async function list() {
  const gallery = await screen.findByRole("list", { name: "Figures and tables" });
  await within(gallery).findAllByRole("listitem");
  return gallery;
}
const names = (gallery: HTMLElement) =>
  within(gallery)
    .getAllByRole("listitem")
    .map((item) => item.getAttribute("aria-label"));

describe("the gallery", () => {
  it("shows each item with its source and a way back to its place", async () => {
    setUp();
    const gallery = await list();
    expect(names(gallery)).toEqual(["Figure 2", "Table 1", "Untitled"]);
    const figure = within(gallery).getByRole("listitem", { name: "Figure 2" });
    expect(figure).toHaveTextContent("Nest density");
    expect(figure).toHaveTextContent("Yılmaz et al. 2024, p. 3");
    expect(within(figure).getByRole("link", { name: "Open in the PDF" })).toHaveAttribute(
      "href",
      "#/reader/att-1?anchor=anchor-1",
    );
    expect(await within(figure).findByRole("img", { name: "Figure 2" })).toHaveAttribute(
      "src",
      "blob:picture",
    );
  });

  it("filters by kind and by words", async () => {
    const { user } = setUp();
    const gallery = await list();
    await user.click(screen.getByRole("radio", { name: "Tables" }));
    expect(names(gallery)).toEqual(["Table 1"]);
    await user.click(screen.getByRole("radio", { name: "All" }));
    await user.type(screen.getByRole("searchbox", { name: /Filter/ }), "NEST");
    expect(names(gallery)).toEqual(["Figure 2"]);
  });

  it("compares two to four side by side", async () => {
    const { user } = setUp();
    await list();
    const compare = screen.getByRole("button", { name: "Compare" });
    await user.click(screen.getByRole("checkbox", { name: "Choose Figure 2" }));
    expect(compare).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: "Choose Table 1" }));
    await user.click(compare);
    expect(screen.getByRole("heading", { name: "Comparing 2" })).toBeInTheDocument();
    expect(screen.getAllByTestId("compare-pane")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Back to the gallery" }));
    expect(await list()).toBeInTheDocument();
  });

  it("edits and deletes, asking first", async () => {
    const { backend, user } = setUp();
    await list();
    await user.click(screen.getByRole("button", { name: "Edit Figure 2" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit figure or table" });
    const label = within(dialog).getByRole("textbox", { name: "Label, as the paper has it" });
    await user.clear(label);
    await user.type(label, "Şekil 2");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(backend.assets[0]?.label).toBe("Şekil 2");
    });

    await user.click(await screen.findByRole("button", { name: "Delete Table 1" }));
    const ask = await screen.findByRole("alertdialog", { name: "Delete “Table 1”?" });
    await user.click(within(ask).getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(backend.assets.map((a) => a.id)).toEqual(["a1", "a3"]);
    });
  });
});
