// Task 32: the title-abstract screening screen. The end-to-end acceptance (20 records by
// keyboard and by mouse, timing) is in e2e/screening.spec.ts; these check the behaviour.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { criterion, fakeBackend, readyPlatform, review } from "@/test/fakeBackend";
import { fakeScreening, type ScreeningPaper } from "@/test/fakeScreening";

import { useScreeningSession } from "./store";

const papers: ScreeningPaper[] = [
  {
    paper_id: "p1",
    title: "Code review with LLMs",
    abstract: "We study KOD İNCELEME with large language models in industry.",
    authors: ["Ayşe Yılmaz", "Can Demir"],
  },
  { paper_id: "p2", title: "A survey of testing", abstract: "A survey." },
  { paper_id: "p3", title: "Reviews of reviews", abstract: null },
];

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: false, inspectorOpen: false });
  useActiveReviewStore.setState({ activeReviewId: null });
  useScreeningSession.setState({ decided: 0, done: [], pendingNotes: {} });
  window.location.hash = "#/screening";
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
  vi.spyOn(Element.prototype, "clientHeight", "get").mockReturnValue(600);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function open(language: "en" | "tr" = "en") {
  const backend = fakeBackend({ language });
  backend.reviews = [review({ id: "review-1" })];
  backend.criteria["review-1"] = [
    criterion({
      id: "i1",
      kind: "inclusion",
      code: "I1",
      text: "About code review",
      keywords: ["kod inceleme", "code review"],
    }),
    criterion({ id: "e1", kind: "exclusion", code: "E1", text: "A survey", keywords: ["survey"] }),
    criterion({ id: "e2", kind: "exclusion", code: "E2", text: "Not English" }),
  ];
  const screening = fakeScreening(backend, "review-1", papers);
  render(<App platform={readyPlatform} fetch={screening.fetch} />);
  return { backend, screening, user: userEvent.setup() };
}

async function title(text: string) {
  expect(await screen.findByRole("heading", { level: 1, name: text })).toBeVisible();
}

describe("screening in focus mode", () => {
  it("decides by keyboard, moving on to the next undecided record", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");

    await user.keyboard("i");
    await title("A survey of testing");
    await user.keyboard("2"); // E1 has key 2: the inclusion criterion I1 is first
    await title("Reviews of reviews");
    await user.keyboard("m");

    await waitFor(() => {
      expect(screening.decisions.map((d) => [d.paper_id, d.decision, d.criterion_id])).toEqual([
        ["p1", "include", null],
        ["p2", "exclude", "e1"],
        ["p3", "maybe", null],
      ]);
    });
    expect(await screen.findByText("No records left in this view.")).toBeVisible();
    expect(screen.getByText("3 decisions this session")).toBeVisible();
    expect(screen.getByText("3 / 3 decided · 100%")).toBeVisible();
  });

  it("asks for a reason with E and excludes with the chosen one", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");

    await user.keyboard("e");
    const menu = await screen.findByRole("menu");
    await user.click(within(menu).getByRole("menuitem", { name: /E2/ }));

    await waitFor(() => {
      expect(screening.decisions[0]).toMatchObject({ decision: "exclude", criterion_id: "e2" });
    });
  });

  it("decides by mouse, the Skip button included", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");
    const bar = screen.getByRole("toolbar", { name: "Decision" });

    await user.click(within(bar).getByRole("button", { name: "Skip" }));
    await title("A survey of testing");
    await user.click(within(bar).getByRole("button", { name: "Exclude" }));
    await user.click(await screen.findByRole("menuitem", { name: /E1/ }));
    await title("Reviews of reviews");
    await user.click(within(bar).getByRole("button", { name: "Maybe" }));
    // Back round to the skipped one.
    await title("Code review with LLMs");
    await user.click(within(bar).getByRole("button", { name: "Include" }));

    await waitFor(() => {
      expect(screening.decisions.map((d) => [d.paper_id, d.decision])).toEqual([
        ["p2", "exclude"],
        ["p3", "maybe"],
        ["p1", "include"],
      ]);
    });
  });

  it("moves with J and K without deciding", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");

    await user.keyboard("j");
    await title("A survey of testing");
    await user.keyboard("k");
    await title("Code review with LLMs");
    await user.keyboard("{ArrowRight}");
    await title("A survey of testing");

    expect(screening.decisions).toEqual([]);
  });

  it("undoes the last decision and goes back to its record", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");
    await user.keyboard("i");
    await title("A survey of testing");

    await user.keyboard("u");

    await title("Code review with LLMs");
    await waitFor(() => {
      expect(screening.decisions.map((d) => d.decision)).toEqual(["include", "undecided"]);
    });
    expect(await screen.findByText("Undecided", { selector: "span" })).toBeVisible();
  });

  it("highlights the criteria's terms, Turkish letters folded", async () => {
    open();
    await title("Code review with LLMs");
    await screen.findByText("Record 1 / 3");

    const marks = document.querySelectorAll<HTMLElement>("[data-criterion]");
    expect([...marks].map((m) => [m.textContent, m.dataset.criterion])).toEqual([
      ["Code review", "I1"],
      ["KOD İNCELEME", "I1"],
    ]);
  });

  it("keeps a note typed before the decision and sends it with it", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");

    await user.keyboard("n");
    const dialog = await screen.findByRole("dialog", { name: "Screening note" });
    // Screening keys stay quiet while typing the note.
    await user.type(within(dialog).getByRole("textbox"), "check the industry claim");
    await user.click(within(dialog).getByRole("button", { name: "Save note" }));
    expect(await screen.findByText("check the industry claim")).toBeVisible();
    expect(screening.decisions).toEqual([]);

    await user.keyboard("m");

    await waitFor(() => {
      expect(screening.decisions[0]).toMatchObject({
        decision: "maybe",
        note: "check the industry claim",
      });
    });
  });

  it("goes back to the record and says why when a decision fails", async () => {
    const { screening, user } = open();
    await title("Code review with LLMs");
    screening.failNext = "screening.stage_not_reached";

    await user.keyboard("i");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Only records included or marked maybe at title and abstract reach full text.",
    );
    await title("Code review with LLMs");
  });
});

describe("screening in list mode", () => {
  it("decides on the selected row with one key", async () => {
    const { screening, user } = open();
    window.location.hash = "#/screening?mode=list&filter=all";
    await screen.findByRole("table", { name: "Records" });

    await user.keyboard("{ArrowDown}");
    await user.keyboard("m");

    await waitFor(() => {
      expect(screening.decisions[0]).toMatchObject({ paper_id: "p2", decision: "maybe" });
    });
    const row = screen.getByText("A survey of testing").closest('[role="row"]');
    expect(within(row as HTMLElement).getByText("Maybe")).toBeVisible();
  });
});

describe("the screening screen in Turkish", () => {
  it("labels the decision bar and its keys", async () => {
    open("tr");
    await title("Code review with LLMs");
    const bar = screen.getByRole("toolbar", { name: "Karar" });

    expect(within(bar).getByRole("button", { name: "Atla" })).toHaveAttribute(
      "aria-keyshortcuts",
      "ArrowRight",
    );
    expect(within(bar).getByRole("button", { name: "Dahil" })).toHaveAttribute(
      "aria-keyshortcuts",
      "I",
    );
    expect(screen.getByText("Bu oturumda 0 karar")).toBeVisible();
  });
});
