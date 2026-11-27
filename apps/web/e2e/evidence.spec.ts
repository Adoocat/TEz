// Task 53 acceptance against the real backend: a sentence selected in the PDF backs a matrix
// cell; from the cell the PDF opens at that sentence, and from the reader the cell opens again.
import { expect, test, type APIRequestContext } from "@playwright/test";

import { addPdf, backend, makePdf, openApp } from "./helpers";

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

test("cell → the sentence in the PDF → the cell again", async ({ page, request }) => {
  const label = `Heron colonies ${String(Date.now())}`;
  const attachmentId = await addPdf(request, "heron.pdf", makePdf(5, label));
  const { paper_id: paperId } = await api<{ paper_id: string }>(
    request,
    "get",
    `/attachments/${attachmentId}`,
  );
  const review = await api<{ id: string }>(request, "post", "/reviews", { title: label });
  await api(request, "post", `/reviews/${review.id}/records`, { paper_ids: [paperId] });
  for (const stage of ["title_abstract", "full_text"]) {
    await api(request, "post", `/reviews/${review.id}/screening/${stage}/decisions`, {
      paper_id: paperId,
      decision: "include",
    });
  }
  const matrix = await api<{ id: string }>(request, "post", `/reviews/${review.id}/matrices`, {
    name: "Synthesis",
  });
  await api(request, "post", `/matrices/${matrix.id}/columns`, { name: "Findings" });
  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, review.id);

  // In the reader: select a sentence on page 3 and link it to the cell.
  await openApp(page, `/reader/${attachmentId}?page=3`);
  const reader = page.getByRole("document", { name: "heron.pdf" });
  const line = reader
    .getByRole("region", { name: "Page 3", exact: true })
    .getByText(`${label} page 3`, { exact: true });
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
  const dialog = page.getByRole("dialog", { name: "Link to a matrix cell" });
  await dialog.getByRole("button", { name: /Findings/ }).click();
  await expect(page.getByText("Linked to Findings.")).toBeVisible();

  // The reading panel's Matrix tab has the cell, filled with the sentence; it opens the matrix.
  await page.getByRole("radio", { name: "Matrix" }).click();
  await page.getByRole("link", { name: "Open Findings in the matrix" }).click();
  const grid = page.getByRole("grid", { name: "Literature matrix" });
  const cell = grid.getByRole("gridcell", { name: new RegExp(`${label} page 3`) });
  await expect(cell).toHaveAttribute("aria-selected", "true");
  await expect(cell.getByLabel("1 source")).toBeVisible();
  await expect(page.getByText(/100% backed by passages/)).toBeVisible();

  // The panel beside the matrix shows the passage and its page; it opens the PDF there.
  const panel = page.getByRole("region", { name: "Cell evidence" });
  await expect(panel.getByRole("blockquote")).toContainText(`${label} page 3`);
  await expect(panel.getByText("p. 3", { exact: true })).toBeVisible();
  await panel.getByRole("link", { name: "Open in the PDF" }).click();
  const flash = reader.getByTestId("anchor-flash");
  await expect(flash).toBeVisible();
  const [a, b] = [await flash.boundingBox(), await line.boundingBox()];
  if (!a || !b) throw new Error("no box");
  expect(Math.abs(a.y + a.height / 2 - (b.y + b.height / 2))).toBeLessThan(10);

  // And back again: the reader's Matrix tab leads to the same cell.
  await page.getByRole("radio", { name: "Matrix" }).click();
  await page.getByRole("link", { name: "Open Findings in the matrix" }).click();
  await expect(cell).toHaveAttribute("aria-selected", "true");
});
