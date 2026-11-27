// Task 55 acceptance against the real backend: an area drawn in the reader is kept as a figure;
// the gallery shows it with its source, compares and exports, and leads back to the place.
import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { addPdf, makePdf, openApp } from "./helpers";

test("a figure kept from the reader leads back to its place in the PDF", async ({
  page,
  request,
}) => {
  const label = `Egret nests ${String(Date.now())}`;
  const attachmentId = await addPdf(request, "egret.pdf", makePdf(4, label));
  await openApp(page, `/reader/${attachmentId}?page=2`);
  const reader = page.getByRole("document", { name: "egret.pdf" });
  const line = reader
    .getByRole("region", { name: "Page 2", exact: true })
    .getByText(`${label} page 2`, { exact: true });
  await expect(line).toBeVisible();

  // Draw around the line with the figure tool.
  await page.getByRole("button", { name: "Keep a figure or table" }).click();
  const box = await line.boundingBox();
  if (!box) throw new Error("no box");
  await page.mouse.move(box.x - 8, box.y - 8);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width + 8, box.y + box.height + 8, { steps: 6 });
  await page.mouse.up();
  const dialog = page.getByRole("dialog", { name: "Keep a figure or table" });
  await expect(dialog.getByRole("img", { name: "The marked area" })).toBeVisible();
  await dialog.getByRole("textbox", { name: "Label, as the paper has it" }).fill("Şekil 1");
  await dialog.getByRole("textbox", { name: "Caption" }).fill("Yuvaların dağılımı");
  await dialog.getByRole("button", { name: "Keep" }).click();
  await expect(page.getByText("Şekil 1 kept.")).toBeVisible();

  // Another one, as a table, to compare with.
  await page.getByRole("button", { name: "Keep a figure or table" }).click();
  await page.mouse.move(box.x, box.y);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height, { steps: 4 });
  await page.mouse.up();
  await dialog.getByText("Table", { exact: true }).click();
  await dialog.getByRole("textbox", { name: "Label, as the paper has it" }).fill("Tablo 1");
  await dialog.getByRole("button", { name: "Keep" }).click();

  // The gallery: both, with their source and a picture.
  await page.getByRole("link", { name: "Open the gallery" }).click();
  const gallery = page.getByRole("list", { name: "Figures and tables" });
  const figure = gallery.getByRole("listitem", { name: "Şekil 1" });
  await expect(figure).toContainText("Yuvaların dağılımı");
  await expect(figure).toContainText("egret, p. 2");
  await expect(figure.getByRole("img", { name: "Şekil 1" })).toBeVisible();
  const width = await figure
    .getByRole("img", { name: "Şekil 1" })
    .evaluate((img: HTMLImageElement) => img.naturalWidth);
  expect(width).toBeGreaterThan(50);

  await page.getByRole("radio", { name: "Tables" }).click();
  await expect(gallery.getByRole("listitem")).toHaveCount(1);
  await page.getByRole("radio", { name: "All" }).click();

  // Side by side, then exported with their sources.
  await page.getByRole("checkbox", { name: "Choose Şekil 1" }).check();
  await page.getByRole("checkbox", { name: "Choose Tablo 1" }).check();
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByTestId("compare-pane")).toHaveCount(2);
  // Each side shows its picture.
  for (const name of ["Şekil 1", "Tablo 1"]) {
    const picture = page.getByRole("region", { name }).getByRole("img", { name });
    await expect
      .poll(() => picture.evaluate((img: HTMLImageElement) => img.naturalWidth))
      .toBeGreaterThan(50);
  }
  await page.getByRole("button", { name: "Back to the gallery" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export" }).click();
  const html = (await readFile(await (await download).path())).toString("utf8");
  expect(html).toContain("<strong>Şekil 1</strong> Yuvaların dağılımı");
  expect(html).toContain("egret, p. 2");
  expect(html).toContain("data:image/png;base64,");

  // From the gallery item back to the place in the PDF.
  await figure.getByRole("link", { name: "Open in the PDF" }).click();
  const flash = reader.getByTestId("anchor-flash");
  await expect(flash).toBeVisible();
  const [a, b] = [await flash.boundingBox(), await line.boundingBox()];
  if (!a || !b) throw new Error("no box");
  expect(Math.abs(a.y + a.height / 2 - (b.y + b.height / 2))).toBeLessThan(12);
});
