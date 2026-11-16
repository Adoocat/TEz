// Task 35: the PRISMA diagram screen and the review panel's summary, both from Task 34's counts.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";
import { sampleCounts } from "@/test/prismaFixtures";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: "review-1" });
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

function backendWithCounts(): FakeBackend {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review({ id: "review-1", title: "LLM Code Review SLR" }));
  backend.prismaCounts["review-1"] = sampleCounts;
  return backend;
}

function open(backend: FakeBackend, hash: string) {
  window.location.hash = hash;
  return render(<App platform={readyPlatform} fetch={backend.fetch} />);
}

async function diagram() {
  const figure = await screen.findByRole("figure", { name: "PRISMA 2020 flow diagram" });
  await waitFor(() => {
    expect(figure.textContent).toContain("1,425");
  });
  return figure;
}

describe("the PRISMA diagram screen", () => {
  it("draws the review's counts", async () => {
    open(backendWithCounts(), "#/prisma");

    // Long lines wrap onto several lines of the drawing; join them back.
    const text = (await diagram()).textContent.replace(/\s+/g, " ");
    expect(text).toContain("Scopus (n = 842)");
    expect(text).toContain("Backward snowballing, round 1 (n = 40)");
    expect(text).toContain("Theses (n = 5)");
    expect(text).toContain("Studies included in review (n = 23)");
  });

  it("keeps an edited box title and draws it", async () => {
    const user = userEvent.setup();
    const backend = backendWithCounts();
    open(backend, "#/prisma");
    await diagram();

    await user.click(screen.getByRole("button", { name: "Edit box titles" }));
    const form = screen.getByRole("form", { name: "Edit box titles" });
    // Both branches have a "Records screened" box; the first is the databases' one.
    const [databases] = within(form).getAllByLabelText("Records screened");
    if (!databases) throw new Error("no title field");
    await user.type(databases, "Başlığı ve özeti okunan kayıtlar");
    await user.click(within(form).getByRole("button", { name: "Save titles" }));

    expect(backend.requests.at(-1)).toMatchObject({
      method: "PUT",
      path: "/reviews/review-1/prisma/labels",
      body: { labels: { db_screened: "Başlığı ve özeti okunan kayıtlar" } },
    });
    await waitFor(() => {
      expect(
        screen.getByRole("figure", { name: "PRISMA 2020 flow diagram" }).textContent,
      ).toContain("Başlığı ve özeti okunan kayıtlar");
    });
  });

  it("switches to the black-and-white print theme", async () => {
    const user = userEvent.setup();
    open(backendWithCounts(), "#/prisma");
    const figure = await diagram();

    await user.click(screen.getByRole("radio", { name: "Black and white" }));

    expect(figure.innerHTML).toContain("#000000");
  });

  it("asks for a review when none is open", async () => {
    useActiveReviewStore.setState({ activeReviewId: null });
    open(fakeBackend({ language: "en" }), "#/prisma");

    expect(
      await screen.findByText("Choose a review in the top bar to see its diagram."),
    ).toBeVisible();
  });
});

describe("the review panel's PRISMA summary", () => {
  it("shows the same counts and links to the diagram", async () => {
    open(backendWithCounts(), "#/review");

    const summary = await screen.findByRole("region", { name: "PRISMA summary" });
    // Both branches added up: 1,425 + 45 identified, 1,131 + 39 screened.
    expect(await within(summary).findByText("1,470")).toBeVisible();
    expect(within(summary).getByText("1,170")).toBeVisible();
    expect(within(summary).getByText("23")).toBeVisible();
    expect(within(summary).getByRole("link", { name: "Open the diagram" })).toHaveAttribute(
      "href",
      "#/prisma",
    );
  });
});
