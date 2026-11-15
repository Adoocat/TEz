// Task 24: the creation wizard (PRISMA 2020 by default) and the review panel (design 5.1).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useSearchView } from "@/features/search/store";
import {
  fakeBackend,
  overview,
  readyPlatform,
  review,
  reviewOverview,
  type FakeBackend,
} from "@/test/fakeBackend";

import { useActiveReviewStore } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useSearchView.setState({ activeSearchId: null, selectedPaperId: null });
  window.location.hash = "#/review";
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

function open(backend: FakeBackend) {
  return render(<App platform={readyPlatform} fetch={backend.fetch} />);
}

describe("the review wizard", () => {
  it("creates a PRISMA 2020 review with its questions and protocol note", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "en" });
    open(backend);

    expect(await screen.findByText(/There is no review yet/)).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Title" }), "LLM Kod İnceleme");
    expect(screen.getByRole("radio", { name: "PRISMA 2020" })).toBeChecked();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.type(
      screen.getByRole("textbox", { name: "Research question 1" }),
      "Hangi teknikler kullanılıyor?",
    );
    await user.click(screen.getByRole("button", { name: "Add question" }));
    await user.type(
      screen.getByRole("textbox", { name: "Research question 2" }),
      "Nasıl değerlendiriliyor?",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.type(screen.getByRole("textbox", { name: "Protocol note" }), "OSF kaydı");
    await user.click(screen.getByRole("button", { name: "Create review" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "LLM Kod İnceleme" }),
    ).toBeVisible();
    expect(
      backend.requests.find((r) => r.method === "POST" && r.path === "/reviews")?.body,
    ).toEqual({
      title: "LLM Kod İnceleme",
      method: "prisma2020",
      research_questions: ["Hangi teknikler kullanılıyor?", "Nasıl değerlendiriliyor?"],
      protocol: "OSF kaydı",
    });
  }, 15_000);

  it("can create from the first step, and Kitchenham stays a choice", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "en" });
    open(backend);

    await user.type(await screen.findByRole("textbox", { name: "Title" }), "SLR");
    await user.click(screen.getByRole("radio", { name: "Kitchenham SLR" }));
    await user.click(screen.getByRole("button", { name: "Create review" }));

    expect(await screen.findByRole("heading", { level: 1, name: "SLR" })).toBeVisible();
    expect(backend.reviews).toMatchObject([
      { method: "kitchenham_slr", research_questions: [], protocol: null },
    ]);
  });

  it("drops a removed question", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "en" });
    open(backend);

    await user.type(await screen.findByRole("textbox", { name: "Title" }), "SLR");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.type(screen.getByRole("textbox", { name: "Research question 1" }), "First");
    await user.click(screen.getByRole("button", { name: "Add question" }));
    await user.type(screen.getByRole("textbox", { name: "Research question 2" }), "Second");
    await user.click(screen.getByRole("button", { name: "Remove research question 1" }));
    await user.click(screen.getByRole("button", { name: "Create review" }));

    await screen.findByRole("heading", { level: 1, name: "SLR" });
    expect(backend.reviews[0]?.research_questions).toEqual(["Second"]);
  });
});

describe("the review panel", () => {
  function withPanel() {
    const backend = fakeBackend({ language: "en" });
    backend.reviews.push(
      review({
        method: "prisma2020",
        research_questions: ["Which techniques are used?", "How are they evaluated?"],
        protocol: "Registered on OSF.",
      }),
    );
    backend.reviewOverviews["review-1"] = reviewOverview({
      records: 1425,
      stages: [
        {
          stage: "title_abstract",
          eligible: 1425,
          decided: 214,
          pending: 1211,
          included: 120,
          excluded: 80,
          maybe: 14,
        },
        {
          stage: "full_text",
          eligible: 134,
          decided: 0,
          pending: 134,
          included: 0,
          excluded: 0,
          maybe: 0,
        },
      ],
    });
    backend.searchHistory = [
      overview({ search_id: "s2", query: "LLM AND review", unique: 412 }),
      overview({ search_id: "s1", query: "", file_name: "scopus.csv", unique: 90 }),
    ];
    return backend;
  }

  it("shows the questions, each stage's waiting count and a way to carry on", async () => {
    open(withPanel());

    expect(
      await screen.findByRole("heading", { level: 1, name: "LLM Code Review SLR" }),
    ).toBeVisible();
    expect(screen.getByText("PRISMA 2020")).toBeVisible();
    expect(screen.getByText("Registered on OSF.")).toBeVisible();
    const questions = screen.getByRole("region", { name: "Research questions" });
    expect(within(questions).getByText("RQ2")).toBeVisible();
    expect(within(questions).getByText("How are they evaluated?")).toBeVisible();

    const stages = screen.getByRole("region", { name: "Stages" });
    expect(await within(stages).findByText("1,425 records in the review")).toBeVisible();
    expect(within(stages).getByText("1,211 waiting")).toBeVisible();
    expect(within(stages).getByText(/214 \/ 1,425 decided/)).toBeVisible();
    expect(within(stages).getByText("134 waiting")).toBeVisible();
    expect(
      within(stages).getByRole("link", { name: "Continue Title-abstract screening" }),
    ).toHaveAttribute("href", "#/screening?stage=title_abstract");
    expect(
      within(stages).getByRole("link", { name: "Continue Full-text screening" }),
    ).toHaveAttribute("href", "#/screening?stage=full_text");
    expect(
      within(stages).getByRole("progressbar", { name: "Title-abstract screening" }),
    ).toHaveAttribute("aria-valuenow", "214");

    expect(screen.getByRole("region", { name: "PRISMA summary" })).toBeVisible();
  });

  it("lists the latest searches and opens one", async () => {
    const user = userEvent.setup();
    open(withPanel());

    const searches = await screen.findByRole("region", { name: "Recent searches" });
    expect(await within(searches).findByText("scopus.csv")).toBeVisible();
    await user.click(within(searches).getByRole("button", { name: /LLM AND review/ }));

    expect(useSearchView.getState().activeSearchId).toBe("s2");
    expect(window.location.hash).toBe("#/search");
  });

  it("is reached from the navigation rail", async () => {
    const user = userEvent.setup();
    window.location.hash = "#/library";
    open(withPanel());

    const nav = await screen.findByRole("navigation", { name: "Main navigation" });
    await user.click(within(nav).getByRole("link", { name: "Review" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "LLM Code Review SLR" }),
    ).toBeVisible();
  });
});
