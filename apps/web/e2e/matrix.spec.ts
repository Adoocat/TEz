// Task 52 acceptance against the real backend: the matrix is made and filled from the keyboard,
// a type change keeps what it cannot convert, undo works; 100 papers × 15 columns scroll
// smoothly.
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import { backend, openApp } from "./helpers";

interface Queue {
  items: { paper_id: string; title: string }[];
}

async function api<T>(
  request: APIRequestContext,
  method: "get" | "post" | "put",
  path: string,
  data?: unknown,
): Promise<T> {
  const { api: base, headers } = backend();
  const response = await request[method](`${base}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${method} ${path}: ${await response.text()}`);
  return (await response.json()) as T;
}

/** A review with `count` papers, all included at full text, in title order. */
async function includedPapers(request: APIRequestContext, title: string, count: number) {
  const review = await api<{ id: string }>(request, "post", "/reviews", { title });
  const stamp = String(Date.now());
  const ris = Array.from({ length: count }, (_, index) =>
    [
      "TY  - JOUR",
      `TI  - Study ${String(index + 1).padStart(3, "0")} on wetland ${stamp}`,
      "AU  - Yılmaz, Ayşe",
      `PY  - ${String(2000 + (index % 25))}`,
      `DO  - 10.5555/matrix.${stamp}.${String(index)}`,
      "ER  - ",
      "",
    ].join("\n"),
  ).join("\n");
  await api(request, "post", "/imports", {
    file_name: "matrix.ris",
    content_base64: Buffer.from(ris, "utf8").toString("base64"),
    review_id: review.id,
    add_to_review: true,
  });
  const queue = await api<Queue>(request, "get", `/reviews/${review.id}/screening/title_abstract`);
  for (const stage of ["title_abstract", "full_text"]) {
    for (const item of queue.items) {
      await api(request, "post", `/reviews/${review.id}/screening/${stage}/decisions`, {
        paper_id: item.paper_id,
        decision: "include",
      });
    }
  }
  return { reviewId: review.id, papers: queue.items };
}

async function open(page: Page, reviewId: string) {
  await page.addInitScript((id) => {
    localStorage.setItem(
      "tez.review",
      JSON.stringify({ state: { activeReviewId: id }, version: 0 }),
    );
  }, reviewId);
  await openApp(page, "/matrix");
}

test("a matrix made and filled from the keyboard; a type change keeps what it cannot read", async ({
  page,
  request,
}) => {
  const { reviewId } = await includedPapers(request, `Matrix keys ${String(Date.now())}`, 3);
  await open(page, reviewId);
  await page.getByRole("button", { name: "Create a matrix" }).click();

  await page.getByRole("button", { name: "Add column" }).click();
  const dialog = page.getByRole("dialog", { name: "Add column" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Sample size");
  await dialog.getByRole("button", { name: "Add column" }).click();
  await expect(dialog).toBeHidden();

  const grid = page.getByRole("grid", { name: "Literature matrix" });
  const cell = (row: number) => grid.getByRole("row").nth(row).getByRole("gridcell").first();
  await grid.focus();
  await page.keyboard.type("120");
  await page.keyboard.press("Enter");
  await page.keyboard.type("about 40");
  await page.keyboard.press("Enter");
  await page.keyboard.type("1.420");
  await page.keyboard.press("Enter");
  await expect(cell(1)).toHaveText("120");
  await expect(cell(3)).toHaveText("1.420");

  // Undo and redo the last edit.
  await page.keyboard.press("Control+z");
  await expect(cell(3)).toHaveText("");
  await page.keyboard.press("Control+y");
  await expect(cell(3)).toHaveText("1.420");

  // Text to number: two cells cannot be read without guessing. The dialog names them first.
  await page.getByRole("button", { name: "Column Sample size: menu" }).click();
  await page.getByRole("menuitem", { name: "Edit column" }).click();
  const edit = page.getByRole("dialog", { name: "Edit column" });
  await edit.getByText("Number", { exact: true }).click();
  await edit.getByRole("button", { name: "Save" }).click();
  await expect(edit.getByRole("alert")).toContainText("2 of 3 cells cannot be converted");
  await expect(edit.getByRole("alert")).toContainText("“about 40”");
  await edit.getByRole("button", { name: "Change, keeping those as text" }).click();
  await expect(edit).toBeHidden();

  await expect(cell(1)).toHaveText("120");
  await expect(cell(2)).toHaveAttribute("aria-invalid", "true");
  await expect(cell(2)).toHaveText("about 40");
  // Fixed by writing a number; the mark goes.
  await grid.focus();
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+a");
  await page.keyboard.type("40");
  await page.keyboard.press("Enter");
  await expect(cell(2)).toHaveText("40");
  await expect(cell(2)).not.toHaveAttribute("aria-invalid", "true");
});

test("100 papers × 15 columns: drawn as they come into view, scrolled smoothly", async ({
  page,
  request,
}) => {
  test.setTimeout(180_000);
  const { reviewId, papers } = await includedPapers(
    request,
    `Matrix size ${String(Date.now())}`,
    100,
  );
  const matrix = await api<{ id: string }>(request, "post", `/reviews/${reviewId}/matrices`, {
    name: "Large",
  });
  const columns: string[] = [];
  for (let n = 1; n <= 15; n += 1) {
    const column = await api<{ id: string }>(request, "post", `/matrices/${matrix.id}/columns`, {
      name: `Field ${String(n)}`,
    });
    columns.push(column.id);
  }
  // Every cell filled, a few at a time.
  const writes = papers.flatMap((paper, row) =>
    columns.map(
      (column, index) => () =>
        api(request, "put", `/matrices/${matrix.id}/cells/${paper.paper_id}/${column}`, {
          value: `Value ${String(row + 1)}.${String(index + 1)} with a few words in it`,
        }),
    ),
  );
  for (let at = 0; at < writes.length; at += 25) {
    await Promise.all(writes.slice(at, at + 25).map((write) => write()));
  }

  await open(page, reviewId);
  const grid = page.getByRole("grid", { name: "Literature matrix" });
  await expect(grid.getByRole("gridcell", { name: /Value 1\.1 / })).toBeVisible();
  // Not all 1500 cells are in the page: only the rows in view and a few more.
  const drawn = await grid.getByRole("row").count();
  expect(drawn).toBeLessThan(45);

  // Down to the bottom and back up, a wheel notch (120 px) a frame, then across and back;
  // each frame is timed.
  const frames = await page.evaluate(async () => {
    const scroller = document.querySelector<HTMLElement>("[data-testid=matrix-scroller]");
    if (!scroller) throw new Error("no scroller");
    const steps = (end: number) => {
      const at: number[] = [];
      for (let n = 0; n <= end; n += 120) at.push(n);
      return [...at, ...at.reverse()];
    };
    const times: number[] = [];
    let last = performance.now();
    const frame = async () => {
      await new Promise(requestAnimationFrame);
      const now = performance.now();
      times.push(now - last);
      last = now;
    };
    for (const top of steps(scroller.scrollHeight - scroller.clientHeight)) {
      scroller.scrollTop = top;
      await frame();
    }
    for (const left of steps(scroller.scrollWidth - scroller.clientWidth)) {
      scroller.scrollLeft = left;
      await frame();
    }
    return times;
  });
  frames.sort((a, b) => a - b);
  const at = (q: number) => frames[Math.min(frames.length - 1, Math.floor(q * frames.length))] ?? 0;
  console.log(JSON.stringify({ frames: frames.length, p50: at(0.5), p95: at(0.95), max: at(1) }));
  // The same budget as the reader's 300 pages (development build): most frames within 30 per
  // second, and no long stalls.
  expect(at(0.5)).toBeLessThan(34);
  expect(at(0.95)).toBeLessThan(100);

  // The keyboard reaches the far corner, and edits there.
  await grid.focus();
  await page.keyboard.press("Control+Home");
  await page.keyboard.press("Control+End");
  await expect(grid.getByRole("rowheader", { name: /Study 100 on wetland/ })).toBeVisible();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Control+a");
  await page.keyboard.type("Last one");
  await page.keyboard.press("Enter");
  await expect(grid.getByRole("gridcell", { name: "Last one" })).toBeVisible();
});

test("exported for Excel, Turkish letters intact", async ({ page, request }) => {
  const { reviewId, papers } = await includedPapers(
    request,
    `Matrix export ${String(Date.now())}`,
    1,
  );
  const matrix = await api<{ id: string }>(request, "post", `/reviews/${reviewId}/matrices`, {
    name: "Sentez",
  });
  const column = await api<{ id: string }>(request, "post", `/matrices/${matrix.id}/columns`, {
    name: "Bulgu",
  });
  const paper = papers[0];
  if (!paper) throw new Error("no paper");
  await api(request, "put", `/matrices/${matrix.id}/cells/${paper.paper_id}/${column.id}`, {
    value: "Işık, ğüşöç İĞÜŞÖÇ",
  });
  await open(page, reviewId);
  await page.getByRole("button", { name: "Export" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: "CSV (.csv)" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("Sentez.csv");
  const path = await file.path();
  const { readFile } = await import("node:fs/promises");
  const data = await readFile(path);
  expect([...data.subarray(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
  const text = data.subarray(3).toString("utf8");
  expect(text.split("\r\n")[0]).toBe("Paper,Title,Year,Bulgu");
  expect(text).toContain("Işık, ğüşöç İĞÜŞÖÇ");
});
