// Task 41 on the review panel: export my decisions under my name, import a colleague's file
// and read what matched.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FetchLike } from "@/app/backend";
import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

import { useReviewerName } from "./ReviewersPanel";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const file = {
  format: "tez.screening-decisions",
  version: 1,
  exported_at: "2026-11-17T10:00:00Z",
  app_version: "0.1.0",
  reviewer: "Ayşe",
  review: { id: "r", title: "SLR", method: "prisma2020" },
  criteria: [],
  records: [],
  decisions: [{ id: "d1" }, { id: "d2" }],
};

function withDecisions(backend: FakeBackend, imported: string[]): FetchLike {
  return async (request) => {
    const url = new URL(request.url, "http://test");
    if (url.pathname === "/reviews/review-1/decisions/export") {
      imported.push(`export:${url.searchParams.get("reviewer") ?? ""}`);
      return json(file);
    }
    if (url.pathname === "/reviews/review-1/decisions/import") {
      const body = (await request.clone().json()) as { content: string };
      imported.push(body.content);
      return json({
        reviewer: "Ayşe",
        records: 3,
        matched: 2,
        added: 3,
        corrected: 0,
        unchanged: 0,
        withdrawn: 0,
        unmatched: [{ ref: "x", title: "A Study Only Ayşe Found", problem: "not_found" }],
        unknown_criteria: [{ code: "E9", decisions: 1 }],
        skipped: [],
      });
    }
    return backend.fetch(request);
  };
}

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: "review-1" });
  useReviewerName.setState({ name: "" });
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

describe("the two-reviewer panel", () => {
  it("exports my decisions under my name and imports a colleague's file", async () => {
    const saveFile = vi.fn(() => Promise.resolve());
    const backend = fakeBackend({ language: "en" });
    backend.reviews.push(review({ id: "review-1" }));
    const calls: string[] = [];
    render(<App platform={{ ...readyPlatform, saveFile }} fetch={withDecisions(backend, calls)} />);
    const user = userEvent.setup();

    const exportButton = await screen.findByRole("button", { name: "Export my decisions" });
    expect(exportButton).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Your name in the file" }), "Demirkan D.");
    await user.click(exportButton);

    expect(await screen.findByText("decisions-demirkan-d.json saved (2 decisions).")).toBeVisible();
    expect(calls).toEqual(["export:Demirkan D."]);
    expect(saveFile).toHaveBeenCalledWith(
      "decisions-demirkan-d.json",
      `${JSON.stringify(file, null, 2)}\n`,
      "application/json",
    );

    await user.upload(
      screen.getByTestId("decision-file"),
      new File(['{"format":"tez.screening-decisions"}'], "ayse.json", { type: "application/json" }),
    );

    expect(await screen.findByText("Ayşe: 2 of 3 records found in this review.")).toBeVisible();
    expect(calls.at(-1)).toBe('{"format":"tez.screening-decisions"}');
    expect(screen.getByText("A Study Only Ayşe Found — not in the library")).toBeVisible();
    expect(screen.getByText(/Criterion codes this review lacks.*E9 \(1\)/)).toBeVisible();
  });
});
