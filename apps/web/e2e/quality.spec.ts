// Task 38 acceptance against the real backend: the stage is hidden on the review panel while
// it is off; a question set with the review's own scale and a bundled template are each used
// to assess the studies included at full text.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { backend, openApp } from "./helpers";

interface Queue {
  items: { paper_id: string; title: string }[];
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

/** A review whose first two records are included at full text and the third is not. */
async function makeReview(request: APIRequestContext, title: string) {
  const review = await api<{ id: string }>(request, "post", "/reviews", { title });
  const stamp = String(Date.now());
  // Titles far apart, so deduplication keeps three records.
  const ris = [
    "Included: telehealth outcomes in rural clinics",
    "Included: peer tutoring in secondary schools",
    "Left out: archival sources of Ottoman land law",
  ]
    .map((name) =>
      [
        "TY  - JOUR",
        `TI  - ${name} ${stamp}`,
        "AU  - Yılmaz, Ayşe",
        "PY  - 2024",
        "ER  - ",
        "",
      ].join("\n"),
    )
    .join("\n");
  await api(request, "post", "/imports", {
    file_name: "quality.ris",
    content_base64: Buffer.from(ris, "utf8").toString("base64"),
    review_id: review.id,
    add_to_review: true,
  });
  const queue = await api<Queue>(request, "get", `/reviews/${review.id}/screening/title_abstract`);
  const included = queue.items.filter((item) => item.title.startsWith("Included"));
  for (const item of queue.items) {
    await api(request, "post", `/reviews/${review.id}/screening/title_abstract/decisions`, {
      paper_id: item.paper_id,
      decision: "include",
    });
  }
  for (const item of included) {
    await api(request, "post", `/reviews/${review.id}/screening/full_text/decisions`, {
      paper_id: item.paper_id,
      decision: "include",
    });
  }
  return review.id;
}

async function open(page: Page, reviewId: string, route: string) {
  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, reviewId);
  await openApp(page, route);
}

test("the panel shows the quality stage only while it is on", async ({ page, request }) => {
  const reviewId = await makeReview(request, `Quality panel ${String(Date.now())}`);
  await open(page, reviewId, "/review");

  const stages = page.getByRole("region", { name: "Stages" });
  const toggle = stages.getByRole("checkbox", { name: "Quality assessment stage" });
  await expect(toggle).not.toBeChecked();
  await expect(stages.getByRole("link", { name: "Continue Quality assessment" })).toHaveCount(0);

  await toggle.click();
  const card = stages.getByRole("link", { name: "Continue Quality assessment" });
  await expect(card).toBeVisible();
  await expect(stages.getByText(/0 \/ 2 assessed/)).toBeVisible();

  await toggle.click();
  await expect(card).toHaveCount(0);
});

test("a custom-scale question set, end to end", async ({ page, request }) => {
  const reviewId = await makeReview(request, `Quality custom ${String(Date.now())}`);
  await open(page, reviewId, "/quality");

  await page.getByRole("button", { name: "Turn on quality assessment" }).click();
  await page
    .getByRole("textbox", { name: "Questions, one per line" })
    .fill("Is the aim clear?\nIs the sample adequate?");
  await page.getByRole("combobox", { name: "Start from" }).selectOption("custom");
  await page.getByRole("textbox", { name: "Option 1 label" }).fill("Strong");
  await page.getByRole("spinbutton", { name: "Option 1 score" }).fill("2");
  await page.getByRole("textbox", { name: "Option 2 label" }).fill("Weak");
  await page.getByRole("spinbutton", { name: "Option 2 score" }).fill("0");
  await page.getByRole("button", { name: "Add 2 questions" }).click();
  await expect(
    page.getByRole("region", { name: "Questions" }).getByText("Is the sample adequate?"),
  ).toBeVisible();

  await page.getByRole("radio", { name: "Assess" }).click();
  const list = page.getByRole("list", { name: "Included studies" });
  await expect(list.getByRole("button")).toHaveCount(2);
  await expect(list.getByText(/Left out/)).toHaveCount(0);

  await page.getByRole("group", { name: /Q1/ }).getByText("Strong").click();
  await page.getByRole("group", { name: /Q2/ }).getByText("Weak").click();
  await expect(list.getByText("2 / 2 answered")).toBeVisible();
  await expect(list.getByText("Score 2 / 4")).toBeVisible();

  // The answers are the server's: a reload shows them again.
  await page.reload();
  await page.getByRole("radio", { name: "Assess" }).click();
  await expect(
    page.getByRole("list", { name: "Included studies" }).getByText("Score 2 / 4"),
  ).toBeVisible();
});

test("a bundled template, end to end", async ({ page, request }) => {
  const reviewId = await makeReview(request, `Quality template ${String(Date.now())}`);
  await open(page, reviewId, "/quality");

  await page.getByRole("button", { name: "Turn on quality assessment" }).click();
  await page
    .getByRole("button", {
      name: "Add the questions of Quality Assessment Tool for Case Series Studies",
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Questions" }).getByText("Were the cases consecutive?"),
  ).toBeVisible();

  await page.getByRole("radio", { name: "Assess" }).click();
  const list = page.getByRole("list", { name: "Included studies" });
  for (let n = 1; n <= 9; n += 1) {
    await page
      .getByRole("group", { name: new RegExp(`^Q${String(n)}\\b`) })
      .getByRole("radio", { name: n <= 6 ? "Yes" : "No", exact: true })
      .click();
  }
  await page
    .getByRole("group", { name: /Quality rating/ })
    .getByRole("radio", { name: "Fair", exact: true })
    .click();

  await expect(list.getByText("10 / 10 answered")).toBeVisible();
  // Six "Yes" of nine items; the overall rating has no score.
  await expect(list.getByText("Score 6 / 9")).toBeVisible();
});
