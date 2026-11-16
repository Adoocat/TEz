// Task 38: a custom-scale question set and a template, each end to end on the screen, and
// the review panel shows the optional stage only while it is on.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review } from "@/test/fakeBackend";
import { fakeQuality } from "@/test/fakeQuality";

const papers = [
  { paper_id: "p1", title: "Yapay zekâ ile kod incelemesi", year: 2024, first_author: "Yılmaz" },
  { paper_id: "p2", title: "Second study", year: 2023, first_author: "Smith" },
];

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  // jsdom has no layout; the virtualized study list needs a size to decide which rows to draw.
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
  vi.spyOn(Element.prototype, "clientWidth", "get").mockReturnValue(900);
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
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function setUp(hash: string, language: "en" | "tr" = "en") {
  window.location.hash = hash;
  const backend = fakeBackend({ language });
  backend.reviews.push(review({ method: "prisma2020" }));
  const quality = fakeQuality(backend, "review-1", papers);
  render(<App platform={readyPlatform} fetch={quality.fetch} />);
  return { backend, quality, user: userEvent.setup() };
}

describe("the review panel", () => {
  it("hides the quality stage while it is off and shows it once turned on", async () => {
    const { quality, user } = setUp("#/review");

    const stages = await screen.findByRole("region", { name: "Stages" });
    const toggle = await within(stages).findByRole("checkbox", {
      name: "Quality assessment stage",
    });
    await vi.waitFor(() => {
      expect(toggle).toBeEnabled();
    });
    expect(toggle).not.toBeChecked();
    expect(within(stages).queryByRole("progressbar", { name: "Quality assessment" })).toBeNull();

    await user.click(toggle);

    expect(
      await within(stages).findByRole("progressbar", { name: "Quality assessment" }),
    ).toBeVisible();
    expect(quality.enabled).toBe(true);
    expect(within(stages).getByText("0 / 2 assessed", { exact: false })).toBeVisible();
    expect(
      within(stages).getByRole("link", { name: "Continue Quality assessment" }),
    ).toHaveAttribute("href", "#/quality");

    await user.click(toggle);
    await vi.waitFor(() => {
      expect(within(stages).queryByRole("progressbar", { name: "Quality assessment" })).toBeNull();
    });
  });
});

describe("the quality screen", () => {
  it("assesses with the review's own questions and scale", async () => {
    const { quality, user } = setUp("#/quality");

    await user.click(await screen.findByRole("button", { name: "Turn on quality assessment" }));
    await user.type(
      await screen.findByRole("textbox", { name: "Questions, one per line" }),
      "Is the aim clear?{Enter}Is the sample adequate?",
    );
    await user.selectOptions(screen.getByRole("combobox", { name: "Start from" }), "custom");
    const label1 = screen.getByRole("textbox", { name: "Option 1 label" });
    await user.clear(label1);
    await user.type(label1, "Strong");
    await user.type(screen.getByRole("spinbutton", { name: "Option 1 score" }), "2");
    const label2 = screen.getByRole("textbox", { name: "Option 2 label" });
    await user.clear(label2);
    await user.type(label2, "Weak");
    await user.type(screen.getByRole("spinbutton", { name: "Option 2 score" }), "0");
    await user.click(screen.getByRole("button", { name: "Add 2 questions" }));

    const questions = await screen.findByRole("region", { name: "Questions" });
    expect(await within(questions).findByText("Is the sample adequate?")).toBeVisible();
    expect(quality.questions[0]?.scale).toEqual([
      { value: "o1", label: "Strong", score: 2 },
      { value: "o2", label: "Weak", score: 0 },
    ]);

    await user.click(screen.getByRole("radio", { name: "Assess" }));
    const list = await screen.findByRole("list", { name: "Included studies" });
    expect(within(list).getByText("Second study")).toBeVisible();
    const q1 = await screen.findByRole("group", { name: /Q1.*Is the aim clear\?/ });
    await user.click(within(q1).getByRole("radio", { name: "Strong" }));
    await user.type(screen.getByRole("textbox", { name: "Note for Q1" }), "Stated in the intro");
    await user.tab();

    expect(await within(list).findByText("1 / 2 answered")).toBeVisible();
    expect(within(list).getByText("Score 2 / 4")).toBeVisible();
    expect(quality.answers.p1?.["question-1"]).toMatchObject({
      answer: "o1",
      note: "Stated in the intro",
    });
  }, 15_000);

  it("starts from a bundled template with labels in the app language", async () => {
    const { backend, quality, user } = setUp("#/quality", "tr");
    quality.enabled = true;

    const template = await screen.findByRole("button", {
      name: "Quality Assessment Tool for Case Series Studies sorularını ekle",
    });
    expect(screen.getByText(/Public domain/)).toBeVisible();
    await user.click(template);

    expect(
      backend.requests.find((r) => r.path.endsWith("/templates/nhlbi_case_series"))?.body,
    ).toEqual({ language: "tr" });
    const questions = await screen.findByRole("region", { name: "Sorular" });
    expect(await within(questions).findByText("Were the cases consecutive?")).toBeVisible();
    expect(quality.questions.map((q) => q.template)).toEqual([
      "nhlbi_case_series",
      "nhlbi_case_series",
      "nhlbi_case_series",
    ]);

    await user.click(screen.getByRole("radio", { name: "Değerlendir" }));
    const q3 = await screen.findByRole("group", { name: /S3.*Quality rating/ });
    await user.click(within(q3).getByRole("radio", { name: "Orta" }));
    const q1 = screen.getByRole("group", { name: /S1/ });
    await user.click(within(q1).getByRole("radio", { name: "Evet" }));

    const list = screen.getByRole("list", { name: "Dahil edilen çalışmalar" });
    expect(await within(list).findByText("2 / 3 yanıtlandı")).toBeVisible();
    // The rating has no score: one "Yes" out of the two scored items.
    expect(within(list).getByText("Puan 1 / 2")).toBeVisible();
  }, 15_000);

  it("refuses to delete an answered question and says why", async () => {
    const { quality, user } = setUp("#/quality");
    quality.enabled = true;
    quality.questions.push({
      id: "q-used",
      text: "Used question",
      guidance: null,
      scale: [
        { value: "yes", label: "Yes", score: 1 },
        { value: "no", label: "No", score: 0 },
      ],
      sort_order: 0,
      template: null,
    });
    quality.answers.p1 = {
      "q-used": {
        question_id: "q-used",
        answer: "yes",
        note: null,
        updated_at: "2026-11-16T10:00:00+00:00",
      },
    };

    await user.click(await screen.findByRole("radio", { name: "Question set" }));
    await user.click(await screen.findByRole("button", { name: "Delete Q1" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/has answers/);
    expect(quality.questions).toHaveLength(1);
  });
});
