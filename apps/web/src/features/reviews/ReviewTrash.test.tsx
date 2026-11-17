// Deleting a review moves it to the trash; the trash brings it back.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

import { useActiveReviewStore } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: "review-2" });
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

function twoReviews(): FakeBackend {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(
    review({ id: "review-1", title: "Kept review" }),
    review({ id: "review-2", title: "Test review" }),
  );
  return backend;
}

describe("deleting a review", () => {
  it("asks first, moves it to the trash and opens another one", async () => {
    const user = userEvent.setup();
    const backend = twoReviews();
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    await screen.findByRole("heading", { level: 1, name: "Test review" });
    await user.click(screen.getByRole("button", { name: "Delete review" }));
    const dialog = screen.getByRole("alertdialog", { name: "Delete \u201cTest review\u201d?" });
    expect(within(dialog).getByText(/are not deleted/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Delete review" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Kept review" })).toBeVisible();
    expect(backend.requests).toContainEqual(
      expect.objectContaining({ method: "DELETE", path: "/reviews/review-2" }),
    );
    const trash = await screen.findByRole("region", { name: "Deleted review (1)" });
    expect(within(trash).getByText("Test review")).toBeVisible();
  });

  it("cancelling keeps the review", async () => {
    const user = userEvent.setup();
    const backend = twoReviews();
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    await screen.findByRole("heading", { level: 1, name: "Test review" });
    await user.click(screen.getByRole("button", { name: "Delete review" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("heading", { level: 1, name: "Test review" })).toBeVisible();
    expect(backend.requests.some((r) => r.method === "DELETE")).toBe(false);
  });

  it("restores a review from the trash and opens it", async () => {
    const user = userEvent.setup();
    const backend = twoReviews();
    backend.reviews[1] = review({
      id: "review-2",
      title: "Test review",
      deleted_at: "2026-11-18T10:00:00Z",
    });
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    const trash = await screen.findByRole("region", { name: "Deleted review (1)" });
    await user.click(within(trash).getByRole("button", { name: "Restore Test review" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Test review" })).toBeVisible();
    expect(screen.queryByRole("region", { name: /Deleted review/ })).not.toBeInTheDocument();
  });
});
