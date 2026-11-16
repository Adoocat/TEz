// Task 32 acceptance: 20 records screened by keyboard only, the same 20 by mouse only (the
// Skip button included), and the next record on screen within 100 ms of a decision.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { backend, openApp } from "./helpers";

const RECORDS = 20;

interface Queue {
  counts: Record<string, number>;
  items: { paper_id: string; title: string; state: string }[];
}

async function api<T>(
  request: APIRequestContext,
  method: "get" | "post",
  path: string,
  data?: unknown,
): Promise<T> {
  const { api: base, headers } = backend();
  const response = await request[method](`${base}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${method} ${path}: ${await response.text()}`);
  return (await response.json()) as T;
}

/** A review with criteria; with `papers`, those papers, else 20 imported ones. */
async function makeReview(request: APIRequestContext, title: string, papers?: string[]) {
  const review = await api<{ id: string }>(request, "post", "/reviews", { title });
  await api(request, "post", `/reviews/${review.id}/criteria`, {
    kind: "inclusion",
    text: "About screening tools",
    keywords: ["screening"],
  });
  await api(request, "post", `/reviews/${review.id}/criteria`, {
    kind: "exclusion",
    text: "Not a study",
    keywords: ["editorial"],
  });
  if (papers) {
    await api(request, "post", `/reviews/${review.id}/records`, { paper_ids: papers });
  } else {
    const stamp = String(Date.now());
    const ris = Array.from({ length: RECORDS }, (_, n) =>
      [
        "TY  - JOUR",
        `TI  - Screening record ${String(n + 1).padStart(2, "0")} ${stamp}`,
        `AB  - An abstract about screening tools, number ${String(n + 1)}.`,
        "AU  - Yılmaz, Ayşe",
        "PY  - 2024",
        "ER  - ",
        "",
      ].join("\n"),
    ).join("\n");
    await api(request, "post", "/imports", {
      file_name: "screening.ris",
      content_base64: Buffer.from(ris, "utf8").toString("base64"),
      review_id: review.id,
      add_to_review: true,
    });
  }
  return review.id;
}

function queue(request: APIRequestContext, reviewId: string) {
  return api<Queue>(request, "get", `/reviews/${reviewId}/screening/title_abstract`);
}

async function openScreening(page: Page, reviewId: string) {
  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, reviewId);
  await openApp(page, "/screening?stage=title_abstract");
  await expect(page.getByText(`Record 1 / ${String(RECORDS)}`)).toBeVisible();
}

/** Time from each key press to the next record's title on screen, measured in the page. */
async function watchTransitions(page: Page) {
  await page.evaluate(() => {
    const state = window as unknown as { pressedAt: number; timings: number[] };
    state.timings = [];
    state.pressedAt = 0;
    let last = document.querySelector("main main h1")?.textContent ?? "";
    window.addEventListener(
      "keydown",
      () => {
        state.pressedAt = performance.now();
      },
      { capture: true },
    );
    new MutationObserver(() => {
      const now = document.querySelector("main main h1")?.textContent ?? "";
      if (now !== last && state.pressedAt > 0) {
        state.timings.push(performance.now() - state.pressedAt);
        state.pressedAt = 0;
      }
      last = now;
    }).observe(document.body, { subtree: true, childList: true, characterData: true });
  });
}

test("20 records by keyboard only, then the same 20 by mouse only", async ({ page, request }) => {
  const stamp = String(Date.now());
  const keyboardReview = await makeReview(request, `Keyboard screening ${stamp}`);
  await openScreening(page, keyboardReview);
  await expect(page.locator("main main mark").first()).toBeVisible();
  await watchTransitions(page);

  // Include, exclude with reason 2 (E1), maybe; one record skipped and then decided last.
  const keys = ["i", "2", "m"];
  await page.keyboard.press("ArrowRight");
  for (let n = 0; n < RECORDS; n += 1) {
    const before = await page.locator("main main h1").textContent();
    await page.keyboard.press(keys[n % keys.length] ?? "i");
    if (n < RECORDS - 1) await expect(page.locator("main main h1")).not.toHaveText(before ?? "");
  }
  await expect(page.getByText("No records left in this view.")).toBeVisible();
  await expect(page.getByText(`${String(RECORDS)} / ${String(RECORDS)} decided`)).toBeVisible();

  const timings = await page.evaluate(() => (window as unknown as { timings: number[] }).timings);
  const sorted = [...timings].sort((a, b) => a - b);
  const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1] ?? Infinity;
  test.info().annotations.push({ type: "transition ms", description: sorted.join(", ") });
  expect(sorted.length).toBeGreaterThanOrEqual(RECORDS - 1);
  expect(p95).toBeLessThan(100);

  const byKeyboard = await queue(request, keyboardReview);
  expect(byKeyboard.counts).toMatchObject({ undecided: 0, include: 7, exclude: 7, maybe: 6 });

  // The same 20 papers in a second review, screened with the mouse alone.
  const mouseReview = await makeReview(
    request,
    `Mouse screening ${stamp}`,
    byKeyboard.items.map((item) => item.paper_id),
  );
  // A fresh page, so the app starts with the second review active.
  const mousePage = await page.context().newPage();
  await openScreening(mousePage, mouseReview);
  const bar = mousePage.getByRole("toolbar", { name: "Decision" });
  await bar.getByRole("button", { name: "Skip" }).click();
  for (let n = 0; n < RECORDS; n += 1) {
    const before = await mousePage.locator("main main h1").textContent();
    const choice = n % 3;
    if (choice === 0) await bar.getByRole("button", { name: "Include" }).click();
    if (choice === 1) {
      await bar.getByRole("button", { name: "Exclude" }).click();
      await mousePage.getByRole("menuitem", { name: /E1/ }).click();
    }
    if (choice === 2) await bar.getByRole("button", { name: "Maybe" }).click();
    if (n < RECORDS - 1)
      await expect(mousePage.locator("main main h1")).not.toHaveText(before ?? "");
  }
  await expect(mousePage.getByText("No records left in this view.")).toBeVisible();

  const byMouse = await queue(request, mouseReview);
  expect(byMouse.counts).toMatchObject({ undecided: 0, include: 7, exclude: 7, maybe: 6 });
  expect(byMouse.items.map((item) => item.paper_id)).toEqual(
    byKeyboard.items.map((item) => item.paper_id),
  );
});
