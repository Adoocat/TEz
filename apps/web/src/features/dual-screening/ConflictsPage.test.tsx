// Task 42: the Conflicts tab shows agreement and kappa per stage, both decisions side by side,
// and a reconciled conflict leaves the list.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";
import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

type ConflictView = components["schemas"]["ConflictView"];

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function conflict(paperId: string, title: string): ConflictView {
  return {
    paper_id: paperId,
    title,
    first_author: "Ayşe Yılmaz",
    author_count: 2,
    year: 2021,
    venue: "Eğitim ve Bilim",
    owner: { decision: "include", criterion_code: null, criterion_text: null, note: null },
    other: {
      decision: "exclude",
      criterion_code: "E1",
      criterion_text: "Not empirical",
      note: "Opinion piece",
    },
  };
}

/** The fake backend plus the agreement and conflict endpoints, with two open conflicts. */
function withConflicts(backend: FakeBackend, reconciled: unknown[]): FetchLike {
  let items = [conflict("p1", "Burnout in rural schools"), conflict("p2", "Teacher stress")];
  return async (request) => {
    const url = new URL(request.url, "http://test");
    const base = "/reviews/review-1/decisions";
    if (url.pathname === `${base}/agreement`) {
      return json({
        reviewer: "Ayşe",
        reviewers: ["Ayşe"],
        stages: [
          {
            stage: "title_abstract",
            compared: 10,
            agreed: 7,
            percent: 70,
            kappa: 0.4,
            conflicts: items.length,
          },
          { stage: "full_text", compared: 0, agreed: 0, percent: null, kappa: null, conflicts: 0 },
        ],
      });
    }
    if (url.pathname === `${base}/conflicts/title_abstract`) {
      return json({ reviewer: "Ayşe", stage: "title_abstract", items });
    }
    if (url.pathname === `${base}/conflicts/title_abstract/reconcile`) {
      const body = (await request.clone().json()) as { paper_id: string };
      reconciled.push(body);
      items = items.filter((item) => item.paper_id !== body.paper_id);
      return json({
        id: "d",
        paper_id: body.paper_id,
        stage: "title_abstract",
        decision: "include",
        criterion_id: null,
        note: null,
        reviewer: "consensus",
        supersedes_id: null,
        created_at: "2026-11-17T10:00:00Z",
      });
    }
    if (url.pathname === "/reviews/review-1/screening/title_abstract/criteria") {
      return json([
        {
          id: "c1",
          kind: "exclusion",
          code: "E1",
          text: "Not empirical",
          shortcut: 1,
          keywords: [],
        },
      ]);
    }
    return backend.fetch(request);
  };
}

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: "review-1" });
  window.location.hash = "#/screening/conflicts";
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

describe("the conflicts tab", () => {
  it("shows agreement, both decisions, and empties as conflicts are reconciled", async () => {
    const backend = fakeBackend({ language: "en" });
    backend.reviews.push(review({ id: "review-1" }));
    const reconciled: unknown[] = [];
    render(<App platform={readyPlatform} fetch={withConflicts(backend, reconciled)} />);
    const user = userEvent.setup();

    expect(await screen.findByText("Agreement 70% · Cohen's kappa 0.40")).toBeVisible();
    expect(screen.getByText("No record was decided by both of you.")).toBeVisible();
    const list = await screen.findByRole("list", { name: "Open conflicts" });
    const first = within(list).getAllByRole("listitem")[0];
    if (!first) throw new Error("no conflict shown");
    expect(within(first).getByText("Burnout in rural schools")).toBeVisible();
    expect(within(first).getByText("Ayşe Yılmaz et al. · 2021 · Eğitim ve Bilim")).toBeVisible();
    expect(within(first).getByText("Not empirical")).toBeVisible();
    expect(within(first).getByText("Opinion piece")).toBeVisible();

    await user.click(within(first).getByRole("button", { name: "Included" }));
    expect(reconciled).toEqual([{ paper_id: "p1", decision: "include" }]);

    const next = await screen.findByRole("listitem");
    expect(within(next).getByText("Teacher stress")).toBeVisible();
    await user.click(within(next).getByRole("button", { name: "Excluded" }));
    expect(reconciled.at(-1)).toEqual({
      paper_id: "p2",
      decision: "exclude",
      criterion_id: "c1",
    });

    expect(await screen.findByText("No open conflicts at this stage.")).toBeVisible();
  });
});
