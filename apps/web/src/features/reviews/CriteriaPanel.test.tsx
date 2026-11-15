// Task 25: screening criteria on the review panel — adding, keys that follow the order, and
// archiving a used criterion instead of deleting it.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import {
  criterion,
  fakeBackend,
  readyPlatform,
  review,
  type FakeBackend,
} from "@/test/fakeBackend";

import { useActiveReviewStore } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  window.location.hash = "#/review";
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

function open(backend: FakeBackend) {
  return render(<App platform={readyPlatform} fetch={backend.fetch} />);
}

function withReview() {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  return backend;
}

async function criteriaSection() {
  return screen.findByRole("region", { name: "Screening criteria" });
}

/** Each active row's code with its title-abstract and full-text keys. */
function rows(section: HTMLElement) {
  return within(section)
    .getAllByRole("row")
    .slice(1)
    .map((row) =>
      within(row)
        .getAllByRole("cell")
        .slice(0, 3)
        .map((cell) => cell.textContent.replace(/(Inclusion|Exclusion)$/, "").trim()),
    );
}

describe("screening criteria", () => {
  it("are added with a code of their kind and a stage", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    open(backend);

    const section = await criteriaSection();
    expect(await within(section).findByText("No criteria yet.")).toBeVisible();
    const form = within(section).getByRole("form", { name: "Add criterion" });
    await user.click(within(form).getByRole("radio", { name: "Inclusion" }));
    await user.type(within(form).getByRole("textbox", { name: "Criterion" }), "Empirical study");
    await user.click(within(form).getByRole("button", { name: "Add criterion" }));
    await within(section).findByText("Empirical study");

    await user.click(within(form).getByRole("radio", { name: "Exclusion" }));
    await user.type(within(form).getByRole("textbox", { name: "Criterion" }), "No evaluation");
    await user.selectOptions(within(form).getByRole("combobox", { name: "Stage" }), "Full text");
    await user.click(within(form).getByRole("button", { name: "Add criterion" }));
    await within(section).findByText("No evaluation");

    expect(rows(section)).toEqual([
      ["1", "1", "I1"],
      ["—", "2", "E1"],
    ]);
    expect(backend.requests.filter((r) => r.method === "POST").map((r) => r.body)).toEqual([
      { kind: "inclusion", code: null, text: "Empirical study", stage: null },
      { kind: "exclusion", code: null, text: "No evaluation", stage: "full_text" },
    ]);
  });

  it("renumber their keys when moved", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.criteria["review-1"] = [
      criterion({ id: "a", code: "E1", text: "First" }),
      criterion({ id: "b", code: "E2", text: "Second" }),
      criterion({ id: "c", code: "E3", text: "Third" }),
    ];
    open(backend);

    const section = await criteriaSection();
    await within(section).findByText("Third");
    expect(rows(section).map((row) => row[2])).toEqual(["E1", "E2", "E3"]);

    await user.click(within(section).getByRole("button", { name: "Move E3 up" }));

    await vi.waitFor(() => {
      expect(rows(section)).toEqual([
        ["1", "1", "E1"],
        ["2", "2", "E3"],
        ["3", "3", "E2"],
      ]);
    });
    expect(backend.requests.find((r) => r.method === "PUT")?.body).toEqual({
      criterion_ids: ["a", "c", "b"],
    });
  });

  it("are deleted when unused and archived when a decision cites them", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.criteria["review-1"] = [
      criterion({ id: "a", code: "E1", text: "Cited", used: true }),
      criterion({ id: "b", code: "E2", text: "Unused" }),
    ];
    open(backend);

    const section = await criteriaSection();
    await within(section).findByText("Unused");
    expect(within(section).queryByRole("button", { name: "Delete E1" })).toBeNull();

    await user.click(within(section).getByRole("button", { name: "Delete E2" }));
    await vi.waitFor(() => {
      expect(within(section).queryByText("Unused")).toBeNull();
    });

    await user.click(within(section).getByRole("button", { name: "Archive E1" }));
    expect(await within(section).findByText("archived")).toBeVisible();
    expect(rows(section)).toEqual([["—", "—", "E1"]]);
    expect(within(section).getByRole("button", { name: "Restore E1" })).toBeVisible();
  });

  it("show the backend's reason when a code is taken", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.criteria["review-1"] = [criterion({ id: "a", code: "E1", text: "One" })];
    open(backend);

    const section = await criteriaSection();
    const form = within(section).getByRole("form", { name: "Add criterion" });
    await user.type(within(form).getByRole("textbox", { name: "Code" }), "e1");
    await user.type(within(form).getByRole("textbox", { name: "Criterion" }), "Two");
    await user.click(within(form).getByRole("button", { name: "Add criterion" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "The code E1 is already used in this review.",
    );
  });

  it("can be edited in place", async () => {
    const user = userEvent.setup();
    const backend = withReview();
    backend.criteria["review-1"] = [
      criterion({ id: "a", code: "E1", text: "Old text", stage: "full_text" }),
    ];
    open(backend);

    const section = await criteriaSection();
    await user.click(await within(section).findByRole("button", { name: "Edit E1" }));
    const text = within(section).getAllByRole("textbox", { name: "Criterion" })[0];
    if (!text) throw new Error("no editor");
    await user.clear(text);
    await user.type(text, "New text");
    await user.selectOptions(
      within(section).getAllByRole("combobox", { name: "Stage" })[0] ?? text,
      "Both stages",
    );
    await user.click(within(section).getByRole("button", { name: "Save" }));

    expect(await within(section).findByText("New text")).toBeVisible();
    expect(backend.requests.find((r) => r.method === "PATCH")?.body).toEqual({
      code: "E1",
      text: "New text",
      stage: null,
    });
  });
});
