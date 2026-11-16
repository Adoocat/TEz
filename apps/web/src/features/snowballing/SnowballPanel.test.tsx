// Task 36: the review panel's snowballing section.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review } from "@/test/fakeBackend";

import type { SnowballRound, SnowballSeed } from "./api";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function seed(overrides: Partial<SnowballSeed>): SnowballSeed {
  return {
    paper_id: "p1",
    title: "Seed paper",
    first_author: "Ayşe Yılmaz",
    year: 2024,
    origin: "database",
    round: 0,
    included_at: "full_text",
    traceable: true,
    followed: [],
    ...overrides,
  };
}

const round: SnowballRound = {
  search_id: "s1",
  round: 1,
  started_at: "2026-11-16T10:00:00+00:00",
  directions: ["backward"],
  sources: ["openalex"],
  seeds: 2,
  identified: 40,
  unique: 35,
  added: 30,
  already_in_review: 5,
  runs: [],
};

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
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

function open(seeds: SnowballSeed[], rounds: SnowballRound[] = []) {
  const backend = fakeBackend({ language: "en" });
  backend.reviews = [review({ id: "review-1" })];
  const posted: unknown[] = [];
  const fetch = async (request: Request) => {
    const path = new URL(request.url, "http://test").pathname;
    if (path === "/reviews/review-1/snowball/seeds") return json(seeds);
    if (path === "/reviews/review-1/snowball" && request.method === "GET") return json(rounds);
    if (path === "/reviews/review-1/snowball") {
      posted.push(await request.json());
      return json({ search_id: "s2", round: 2, job_id: "job-1" }, 202);
    }
    return backend.fetch(request);
  };
  render(<App platform={readyPlatform} fetch={fetch} />);
  return { posted, user: userEvent.setup() };
}

async function section() {
  return screen.findByRole("region", { name: "Snowballing" });
}

describe("snowballing on the review panel", () => {
  it("starts a round from the checked seeds, directions and sources", async () => {
    const { posted, user } = open([
      seed({ paper_id: "p1", title: "Seed paper" }),
      seed({ paper_id: "p2", title: "Other paper", included_at: "title_abstract" }),
      seed({ paper_id: "p3", title: "No identifiers", traceable: false }),
    ]);
    const panel = await section();
    const form = within(panel).getByRole("form", { name: "Start a snowballing round" });

    await user.click(await within(form).findByRole("checkbox", { name: /Other paper/ }));
    await user.click(within(form).getByRole("checkbox", { name: "Semantic Scholar" }));
    expect(within(form).getByRole("checkbox", { name: /No identifiers/ })).toBeDisabled();
    await user.click(within(form).getByRole("button", { name: "Start a snowballing round" }));

    await waitFor(() => {
      expect(posted).toEqual([
        {
          paper_ids: ["p1"],
          directions: ["backward", "forward"],
          sources: ["openalex"],
          limit: 1000,
          initiated_via: "gui",
        },
      ]);
    });
    expect(await within(form).findByRole("status")).toHaveTextContent(
      "Round 2 is running in the background…",
    );
  });

  it("lists past rounds with derived counts", async () => {
    open([seed({})], [round]);
    const panel = await section();

    const history = await within(panel).findByRole("list", { name: "Snowballing rounds" });
    expect(history).toHaveTextContent("Round 1");
    expect(history).toHaveTextContent("2 seeds · 40 found · 30 new · 5 already in the review");
  });

  it("says to include papers first when there are no seeds", async () => {
    open([]);
    const panel = await section();

    expect(
      await within(panel).findByText(
        "Include papers in screening first: snowballing starts from them.",
      ),
    ).toBeVisible();
  });
});
