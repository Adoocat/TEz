// Task 33 acceptance: full-text screening of a record with a PDF (the reader opens beside the
// criteria) and one without ("Find PDFs", then "Full text not retrieved", counted on its
// own). The PRISMA box for it comes with Task 34, whose tests check it there.
import { expect, test, type APIRequestContext } from "@playwright/test";

import { backend, makePdf, openApp } from "./helpers";

async function call<T>(
  request: APIRequestContext,
  path: string,
  data?: unknown,
  method: "get" | "post" = "post",
): Promise<T> {
  const { api, headers } = backend();
  const response = await request[method](`${api}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${path}: ${await response.text()}`);
  return (await response.json()) as T;
}

interface Queue {
  counts: Record<string, number>;
  items: { paper_id: string; title: string }[];
}

test("a record with a PDF and one without, at full text", async ({ page, request }) => {
  const stamp = String(Date.now());
  const review = await call<{ id: string }>(request, "/reviews", {
    title: `Full text ${stamp}`,
  });
  await call(request, `/reviews/${review.id}/criteria`, {
    kind: "exclusion",
    text: "No evaluation",
    stage: "full_text",
  });
  const ris = ["With PDF", "Without PDF"]
    .map((title) => `TY  - JOUR\nTI  - ${title} ${stamp}\nPY  - 2024\nER  - \n`)
    .join("\n");
  await call(request, "/imports", {
    file_name: "full-text.ris",
    content_base64: Buffer.from(ris, "utf8").toString("base64"),
    review_id: review.id,
    add_to_review: true,
  });
  const titleAbstract = await call<Queue>(
    request,
    `/reviews/${review.id}/screening/title_abstract`,
    undefined,
    "get",
  );
  const [withPdf, withoutPdf] = titleAbstract.items;
  if (!withPdf || !withoutPdf) throw new Error("the import made no records");
  for (const item of titleAbstract.items) {
    await call(request, `/reviews/${review.id}/screening/title_abstract/decisions`, {
      paper_id: item.paper_id,
      decision: "include",
    });
  }
  const { api, headers } = backend();
  const upload = await request.post(
    `${api}/pdfs?file_name=with-pdf.pdf&paper_id=${withPdf.paper_id}`,
    { headers: { ...headers, "Content-Type": "application/pdf" }, data: makePdf(2, stamp) },
  );
  expect(upload.ok()).toBe(true);

  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, review.id);
  await openApp(page, "/screening?stage=full_text");

  // The first record: its PDF in the reader, the criteria and the decision bar beside it.
  await expect(page.getByRole("heading", { level: 1, name: withPdf.title })).toBeVisible();
  const pane = page.getByRole("region", { name: "Full text" });
  await expect(pane.getByRole("heading", { name: "with-pdf.pdf" })).toBeVisible();
  await expect(pane.locator("canvas").first()).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Criteria" })).toContainText("E1");
  await page.keyboard.press("i");

  // The second: no PDF, so a way to look for one, and "not retrieved".
  await expect(page.getByRole("heading", { level: 1, name: withoutPdf.title })).toBeVisible();
  await expect(pane.getByRole("heading", { name: "No PDF for this record" })).toBeVisible();
  await expect(pane.getByRole("button", { name: "Find PDFs" })).toBeVisible();
  await page.getByRole("button", { name: "Full text not retrieved" }).click();
  await expect(page.getByText("No records left in this view.")).toBeVisible();

  const fullText = await call<Queue>(
    request,
    `/reviews/${review.id}/screening/full_text`,
    undefined,
    "get",
  );
  expect(fullText.counts).toMatchObject({ total: 2, include: 1, not_retrieved: 1, exclude: 0 });
});
