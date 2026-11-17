// Task 40 acceptance against the real backend: the included studies' APA 7 bibliography goes
// to the clipboard, and the search strategy table has every search run of the review.
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

function ris(titles: string[]): string {
  return titles
    .map((title) =>
      [
        "TY  - JOUR",
        `TI  - ${title}`,
        "AU  - Yılmaz, Ayşe",
        "PY  - 2024",
        "JO  - Teaching and Teacher Education",
        "ER  - ",
        "",
      ].join("\n"),
    )
    .join("\n");
}

/** Two database exports imported into a review; one record included at full text. */
async function makeReview(request: APIRequestContext, title: string, stamp: string) {
  const review = await api<{ id: string }>(request, "post", "/reviews", { title });
  const files = [
    {
      source: "Scopus",
      query: 'TITLE-ABS-KEY("teacher burnout")',
      titles: [`Included: teacher burnout in rural schools ${stamp}`],
    },
    {
      source: "ERIC",
      query: "teacher AND burnout",
      titles: [`Left out: archival sources of Ottoman land law ${stamp}`],
    },
  ];
  for (const file of files) {
    await api(request, "post", "/imports", {
      file_name: `${file.source.toLowerCase()}.ris`,
      content_base64: Buffer.from(ris(file.titles), "utf8").toString("base64"),
      review_id: review.id,
      add_to_review: true,
      log: {
        source: file.source,
        query: file.query,
        searched_at: "2026-03-02",
        method: "database",
      },
    });
  }
  const queue = await api<Queue>(request, "get", `/reviews/${review.id}/screening/title_abstract`);
  for (const item of queue.items) {
    await api(request, "post", `/reviews/${review.id}/screening/title_abstract/decisions`, {
      paper_id: item.paper_id,
      decision: "include",
    });
    if (item.title.startsWith("Included")) {
      await api(request, "post", `/reviews/${review.id}/screening/full_text/decisions`, {
        paper_id: item.paper_id,
        decision: "include",
      });
    }
  }
  return review.id;
}

async function open(page: Page, reviewId: string) {
  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, reviewId);
  await openApp(page, "/export");
}

test("the included studies' APA 7 bibliography goes to the clipboard", async ({
  page,
  request,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const stamp = String(Date.now());
  const reviewId = await makeReview(request, `Export APA ${stamp}`, stamp);
  await open(page, reviewId);

  await expect(page.getByRole("radio", { name: /Included studies/ })).toBeChecked();
  await page.getByRole("radio", { name: "Bibliography" }).click();
  await page.getByRole("combobox", { name: "Style" }).selectOption("apa");
  await page.getByRole("radio", { name: "English" }).click();
  const preview = page.getByRole("list", { name: "Preview" });
  await expect(preview.getByRole("listitem")).toHaveCount(1);

  await page.getByRole("button", { name: "Copy to clipboard" }).click();
  await expect(page.getByText("Copied to the clipboard.")).toBeVisible();

  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toBe(
    `Yılmaz, A. (2024). Included: teacher burnout in rural schools ${stamp}. Teaching and Teacher Education.`,
  );
});

test("the strategy table has every search run", async ({ page, request }) => {
  const stamp = String(Date.now());
  const reviewId = await makeReview(request, `Export strategy ${stamp}`, stamp);
  const runs = await api<{ rows: { source: string }[] }>(
    request,
    "get",
    `/export/search-strategy?review_id=${reviewId}`,
  );
  await open(page, reviewId);

  const table = page.getByRole("table");
  // A header row and one row per run.
  await expect(table.getByRole("row")).toHaveCount(1 + runs.rows.length);
  expect(runs.rows.map((row) => row.source)).toEqual(["Scopus", "ERIC"]);
  await expect(table.getByText("Scopus (scopus.ris)")).toBeVisible();
  await expect(table.getByText('TITLE-ABS-KEY("teacher burnout")')).toBeVisible();
  await expect(table.getByText("ERIC (eric.ris)")).toBeVisible();
  await expect(table.getByText("teacher AND burnout")).toBeVisible();
});
