// Task 57 acceptance: search → screening → reading → matrix in one session, through the UI.
// The search is a database export imported as a search run (no test reaches the network);
// the PDFs are added the way a downloaded file is, through the API that a drop calls.
import { expect, test, type APIRequestContext } from "@playwright/test";

import { backend, makePdf, openApp } from "./helpers";

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

interface Queue {
  counts: Record<string, number>;
  items: { paper_id: string; title: string }[];
}

test("search → screening → reading → matrix in one session", async ({ page, request }) => {
  const stamp = String(Date.now());
  const title = `Journey ${stamp}`;
  const papers = ["Stork migration", "Heron colonies", "Editorial on birds"].map(
    (name) => `${name} ${stamp}`,
  );

  // 1. A review through the wizard.
  await openApp(page, "/review");
  await page.getByRole("button", { name: "New review" }).click();
  const wizard = page.getByRole("dialog", { name: "New review" });
  await wizard.getByRole("textbox", { name: "Title" }).fill(title);
  await wizard.getByRole("button", { name: "Next" }).click();
  await wizard.getByRole("textbox", { name: "Research question 1" }).fill("Where do they nest?");
  await wizard.getByRole("button", { name: "Create review" }).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  const reviews = await api<{ id: string; title: string }[]>(request, "get", "/reviews");
  const reviewId = reviews.find((review) => review.title === title)?.id;
  if (!reviewId) throw new Error("the wizard made no review");
  await api(request, "post", `/reviews/${reviewId}/criteria`, {
    kind: "inclusion",
    text: "Field study of birds",
  });
  await api(request, "post", `/reviews/${reviewId}/criteria`, {
    kind: "exclusion",
    text: "Not a study",
  });

  // 2. The search: a Scopus export, logged as a search run.
  const ris = papers
    .map((paper, index) =>
      [
        "TY  - JOUR",
        `TI  - ${paper}`,
        `AB  - An abstract about ${paper.toLowerCase()}.`,
        "AU  - Yılmaz, Ayşe",
        `PY  - ${String(2020 + index)}`,
        `DO  - 10.5555/journey.${stamp}.${String(index)}`,
        "ER  - ",
        "",
      ].join("\n"),
    )
    .join("\n");
  await page.evaluate(() => {
    window.location.hash = "/search";
  });
  await page.getByRole("button", { name: "Import file" }).click();
  const dialog = page.getByRole("dialog", { name: "Import exported results" });
  await dialog.getByLabel("Choose file").setInputFiles({
    name: "scopus.ris",
    mimeType: "application/x-research-info-systems",
    buffer: Buffer.from(ris, "utf8"),
  });
  await expect(dialog.getByText(/3 entries/)).toBeVisible();
  await dialog.getByLabel("Database", { exact: true }).selectOption("Scopus");
  await dialog.getByLabel("Query used").fill("birds AND nesting");
  await dialog.getByRole("button", { name: "Import 3 records" }).click();
  await expect(dialog.getByText(/3 records imported/)).toBeVisible();
  await dialog.getByRole("button", { name: "Close" }).first().click();

  // 3. Title-abstract screening by keyboard: two in, the editorial out with E1 (key 2).
  await page.evaluate(() => {
    window.location.hash = "/screening?stage=title_abstract";
  });
  const heading = page.locator("main main h1");
  for (const paper of papers) {
    await expect(heading).toHaveText(paper);
    await page.keyboard.press(paper.startsWith("Editorial") ? "2" : "i");
  }
  await expect(page.getByText("No records left in this view.")).toBeVisible();

  // 4. The PDFs of the two included papers, then full-text screening beside them.
  const queue = await api<Queue>(request, "get", `/reviews/${reviewId}/screening/full_text`);
  expect(queue.items.map((item) => item.title)).toEqual(papers.slice(0, 2));
  const { api: base, headers } = backend();
  const attachments: string[] = [];
  for (const [index, item] of queue.items.entries()) {
    const upload = await request.post(
      `${base}/pdfs?file_name=paper-${String(index + 1)}.pdf&paper_id=${item.paper_id}`,
      {
        headers: { ...headers, "Content-Type": "application/pdf" },
        data: makePdf(3, item.title),
      },
    );
    expect(upload.ok()).toBe(true);
    attachments.push(((await upload.json()) as { attachment_id: string }).attachment_id);
  }
  await page.evaluate(() => {
    window.location.hash = "/screening?stage=full_text";
  });
  const pane = page.getByRole("region", { name: "Full text" });
  for (const [index, item] of queue.items.entries()) {
    await expect(heading).toHaveText(item.title);
    await expect(
      pane.getByRole("heading", { name: `paper-${String(index + 1)}.pdf` }),
    ).toBeVisible();
    await page.keyboard.press("i");
  }
  await expect(page.getByText("No records left in this view.")).toBeVisible();

  // 5. The matrix: one row for each paper included at full text.
  await page.evaluate(() => {
    window.location.hash = "/matrix";
  });
  await page.getByRole("button", { name: "Create a matrix" }).click();
  await page.getByRole("button", { name: "Add column" }).click();
  const column = page.getByRole("dialog", { name: "Add column" });
  await column.getByRole("textbox", { name: "Name" }).fill("Findings");
  await column.getByRole("button", { name: "Add column" }).click();
  await expect(column).toBeHidden();
  const grid = page.getByRole("grid", { name: "Literature matrix" });
  await expect(grid.getByRole("row")).toHaveCount(3);

  // 6. Reading: a sentence of the first paper backs its Findings cell.
  const first = queue.items[0];
  const firstPdf = attachments[0];
  if (!first || !firstPdf) throw new Error("no included paper");
  await page.evaluate((id) => {
    window.location.hash = `/reader/${id}?page=2`;
  }, firstPdf);
  const reader = page.getByRole("document", { name: "paper-1.pdf" });
  const line = reader
    .getByRole("region", { name: "Page 2", exact: true })
    .getByText(`${first.title} page 2`, { exact: true });
  await expect(line).toBeVisible();
  const box = await line.boundingBox();
  if (!box) throw new Error("no box");
  await page.mouse.move(box.x + 1, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width - 1, box.y + box.height / 2, { steps: 8 });
  await page.mouse.up();
  await page
    .getByRole("toolbar", { name: "Selected text" })
    .getByRole("button", { name: "Link to a matrix cell" })
    .click();
  await page
    .getByRole("dialog", { name: "Link to a matrix cell" })
    .getByRole("button", { name: /Findings/ })
    .click();
  await expect(page.getByText("Linked to Findings.")).toBeVisible();

  // 7. Back in the matrix: the cell holds the sentence; the one filled cell is backed.
  await page.getByRole("radio", { name: "Matrix" }).click();
  await page.getByRole("link", { name: "Open Findings in the matrix" }).click();
  const cell = grid.getByRole("gridcell", { name: new RegExp(`${first.title} page 2`) });
  await expect(cell).toHaveAttribute("aria-selected", "true");
  await expect(cell.getByLabel("1 source")).toBeVisible();
  await expect(
    page.getByText("100% backed by passages (1 of 1 cells; 1 of 1 rows fully)"),
  ).toBeVisible();

  // The counts come from the decisions: 3 screened, 1 excluded, 2 included at full text.
  const titleAbstract = await api<Queue>(
    request,
    "get",
    `/reviews/${reviewId}/screening/title_abstract`,
  );
  expect(titleAbstract.counts).toMatchObject({ total: 3, include: 2, exclude: 1 });
  const fullText = await api<Queue>(request, "get", `/reviews/${reviewId}/screening/full_text`);
  expect(fullText.counts).toMatchObject({ total: 2, include: 2 });
});
