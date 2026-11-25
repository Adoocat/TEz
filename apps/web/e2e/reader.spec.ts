// Task 20 acceptance: a 300-page PDF opens, streams in ranges, scrolls smoothly and keeps
// memory bounded. The numbers are printed so the progress log can record them.
import { expect, test } from "@playwright/test";

import { addPdf, makePdf, openApp } from "./helpers";

test("a 300-page PDF streams, scrolls and stays light", async ({ page, request }) => {
  // About 6 MB: big enough that reading it in ranges shows.
  const pdf = makePdf(300, "Long thesis", 20_000);
  const attachmentId = await addPdf(request, "long-thesis.pdf", pdf);
  let rangeBytes = 0;
  let rangeResponses = 0;
  page.on("response", (response) => {
    if (response.url().includes(`/attachments/${attachmentId}/file`) && response.status() === 206) {
      rangeResponses += 1;
      rangeBytes += Number(response.headers()["content-length"] ?? 0);
    }
  });

  await openApp(page, `/reader/${attachmentId}?page=150`);

  const reader = page.getByRole("document", { name: "long-thesis.pdf" });
  await expect(reader.getByRole("region", { name: "Page 150" })).toBeVisible();
  await expect(page.getByText("of 300")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Page" })).toHaveValue("150");
  // The text layer is there to select and find.
  await expect(reader.getByText("Long thesis page 150", { exact: true })).toBeAttached();
  const openedWith = rangeBytes;

  const heapBefore = await page.evaluate(
    () =>
      (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory?.usedJSHeapSize ??
      0,
  );
  // Scroll the whole document in steps, timing each step's frame.
  const steps = await page.evaluate(async () => {
    const scroller = document.querySelector<HTMLElement>('[data-testid="reader-scroller"]');
    if (!scroller) throw new Error("no scroller");
    const times: number[] = [];
    scroller.scrollTop = 0;
    const frame = () => new Promise<number>((resolve) => requestAnimationFrame(resolve));
    await frame();
    while (scroller.scrollTop + scroller.clientHeight < scroller.scrollHeight - 1) {
      const start = performance.now();
      scroller.scrollTop += 900;
      await frame();
      times.push(performance.now() - start);
    }
    times.sort((a, b) => a - b);
    const at = (q: number) => times[Math.min(times.length - 1, Math.floor(q * times.length))] ?? 0;
    return { count: times.length, p50: at(0.5), p95: at(0.95), max: at(1) };
  });
  await expect(reader.getByRole("region", { name: "Page 300" })).toBeVisible();
  const canvases = await reader.locator("canvas").count();
  const heapAfter = await page.evaluate(
    () =>
      (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory?.usedJSHeapSize ??
      0,
  );

  console.log(
    JSON.stringify({
      fileSize: pdf.length,
      rangeResponses,
      bytesToOpenAtPage150: openedWith,
      bytesAfterScrollingAll: rangeBytes,
      canvasesInDom: canvases,
      heapMbBefore: Math.round(heapBefore / 1e6),
      heapMbAfter: Math.round(heapAfter / 1e6),
      scrollSteps: steps,
    }),
  );
  // Opening at page 150 read only part of the file, in ranges.
  expect(rangeResponses).toBeGreaterThan(0);
  expect(openedWith).toBeLessThan(pdf.length / 2);
  // Only the pages near the screen are drawn.
  expect(canvases).toBeLessThanOrEqual(8);
  expect(steps.p95).toBeLessThan(100);
  if (heapAfter > 0) expect(heapAfter).toBeLessThan(heapBefore + 150e6);
});

test("the reader opens from the library inspector at page 1", async ({ page, request }) => {
  await addPdf(request, "short-paper.pdf", makePdf(3, "Short paper"));
  await openApp(page);

  await page.getByRole("table", { name: "Papers" }).getByText("short paper").first().click();
  await page.getByRole("button", { name: "Open PDF" }).click();

  const reader = page.getByRole("document", { name: "short-paper.pdf" });
  await expect(reader.getByRole("region", { name: "Page 1" })).toBeVisible();
  await expect(page.getByText("of 3")).toBeVisible();
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.getByRole("button", { name: "Fit to width" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("outline, thumbnails, search and page sizes", async ({ page, request }) => {
  const pdf = makePdf(30, "Pelican survey", 0, {
    // A landscape page, and pages turned in the file.
    page: (n) =>
      n === 2 ? { size: [1000, 500] } : n === 3 ? { rotate: 90 } : n === 4 ? { rotate: 180 } : {},
    outline: [
      ["Opening", 1],
      ["Findings", 20],
    ],
  });
  const attachmentId = await addPdf(request, "pelican.pdf", pdf);
  await openApp(page, `/reader/${attachmentId}`);
  const reader = page.getByRole("document", { name: "pelican.pdf" });
  await expect(reader.getByRole("region", { name: "Page 1", exact: true })).toBeVisible();

  // Each page has its own shape, and its text lies on it, turned pages included.
  for (const n of [2, 3, 4]) {
    await page.getByRole("textbox", { name: "Page" }).fill(String(n));
    await page.keyboard.press("Enter");
    const section = reader.getByRole("region", { name: `Page ${String(n)}`, exact: true });
    const line = section.getByText(`Pelican survey page ${String(n)}`, { exact: true });
    await expect(line).toBeVisible();
    const box = await section.boundingBox();
    const text = await line.boundingBox();
    if (!box || !text) throw new Error("no box");
    expect(box.width > box.height).toBe(n !== 4);
    expect(text.x).toBeGreaterThanOrEqual(box.x - 1);
    expect(text.x + text.width).toBeLessThanOrEqual(box.x + box.width + 1);
    expect(text.y).toBeGreaterThanOrEqual(box.y - 1);
    expect(text.y + text.height).toBeLessThanOrEqual(box.y + box.height + 1);
    // The line runs down a page turned by 90 degrees.
    expect(text.height > text.width).toBe(n === 3);
  }

  await page.getByRole("button", { name: "Outline and pages" }).click();
  await page.getByRole("navigation", { name: "Outline" }).getByText("Findings").click();
  await expect(page.getByRole("textbox", { name: "Page" })).toHaveValue("20");
  await page.getByRole("radio", { name: "Pages" }).click();
  await page.getByRole("button", { name: "Go to page 21" }).click();
  await expect(page.getByRole("textbox", { name: "Page" })).toHaveValue("21");

  // Ctrl+F searches the document, not the few pages in the DOM.
  await page.keyboard.press("ControlOrMeta+f");
  await page.getByRole("searchbox", { name: "Search in this document" }).fill("PELİCAN survey");
  await expect(page.getByText("21 of 30")).toBeVisible({ timeout: 45_000 });
  const marked = () =>
    page.evaluate(() =>
      [...(CSS.highlights.get("tez-find-current") ?? [])].map((range) =>
        (range as Range).toString(),
      ),
    );
  await expect.poll(marked).toEqual(["Pelican survey"]);
  await page.getByRole("button", { name: "Next match" }).click();
  await expect(page.getByText("22 of 30")).toBeVisible();
  await expect(reader.getByRole("region", { name: "Page 22" })).toBeVisible();

  // Focus mode: only the document is left.
  await page.keyboard.press("Escape");
  await page.keyboard.press("f");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
});

test("pdf.js finds its fonts and decoders", async ({ page }) => {
  for (const file of [
    "standard_fonts/FoxitSerif.pfb",
    "wasm/openjpeg.wasm",
    "cmaps/UniJIS-UTF16-H.bcmap",
  ]) {
    const response = await page.request.get(`/pdfjs/${file}`);
    expect(response.status(), file).toBe(200);
    expect((await response.body()).length, file).toBeGreaterThan(1000);
  }
  // GPL-2.0: not part of the app (docs/licenses.md).
  const left = await page.request.get("/pdfjs/standard_fonts/LiberationSans-Regular.ttf");
  expect(left.headers()["content-type"]).not.toBe("application/octet-stream");
});
