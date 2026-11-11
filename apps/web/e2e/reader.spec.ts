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
