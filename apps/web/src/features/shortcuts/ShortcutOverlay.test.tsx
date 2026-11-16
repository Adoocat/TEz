// Task 30 acceptance: the `?` overlay lists the shortcut maps, in Turkish and English.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { fakeBackend, readyPlatform } from "@/test/fakeBackend";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  window.location.hash = "#/settings/general";
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

async function openOverlay(language: "tr" | "en") {
  const user = userEvent.setup();
  render(<App platform={readyPlatform} fetch={fakeBackend({ language }).fetch} />);
  await screen.findByRole("heading", { level: 1 });
  await user.keyboard("?");
  return { user, dialog: await screen.findByRole("dialog") };
}

describe("the shortcut overlay", () => {
  it("lists every context's shortcuts in Turkish", async () => {
    const { dialog } = await openOverlay("tr");

    expect(within(dialog).getByRole("heading", { name: "Klavye kısayolları" })).toBeVisible();
    const screening = within(dialog).getByRole("region", { name: "Eleme" });
    expect(within(screening).getByText("Atla").nextSibling).toHaveTextContent("→");
    expect(within(screening).getByText("Hariç tutma gerekçesi").nextSibling).toHaveTextContent(
      "1…9",
    );
    for (const context of ["Her yerde", "Okuyucu", "Listeler"]) {
      expect(within(dialog).getByRole("region", { name: context })).toBeVisible();
    }
  });

  it("speaks English too, and closes with ? again", async () => {
    const { user, dialog } = await openOverlay("en");

    expect(within(dialog).getByRole("heading", { name: "Keyboard shortcuts" })).toBeVisible();
    expect(
      within(dialog).getByText("Go to a screen in the navigation").nextSibling,
    ).toHaveTextContent("Ctrl+1…Ctrl+7");

    await user.keyboard("?");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays shut while typing a question mark in a field", async () => {
    const user = userEvent.setup();
    window.location.hash = "#/search";
    render(<App platform={readyPlatform} fetch={fakeBackend({ language: "en" }).fetch} />);
    const [field] = await screen.findAllByRole("textbox");
    if (!field) throw new Error("the search screen has no text field");

    await user.type(field, "why?");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("goes to the navigation's screens with Ctrl and a number", async () => {
    const user = userEvent.setup();
    render(<App platform={readyPlatform} fetch={fakeBackend({ language: "en" }).fetch} />);
    await screen.findByRole("heading", { level: 1 });

    await user.keyboard("{Control>}2{/Control}");

    expect(window.location.hash).toBe("#/search");
  });
});
