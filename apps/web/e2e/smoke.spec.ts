// Task 21's smoke test: the app comes up against a real backend, its main screens open, a
// preference survives a reload, and a backup runs through the real worker.
import { expect, test } from "@playwright/test";

import { openApp } from "./helpers";

test("the app opens and every main screen answers", async ({ page }) => {
  await openApp(page);

  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await expect(nav).toBeVisible();
  for (const [label, heading] of [
    ["Search", "Systematic search"],
    ["Library", "All papers"],
    ["Reader", "Reader"],
    ["Jobs", "Jobs"],
  ] as const) {
    await nav.getByRole("link", { name: label }).click();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
  await expect(page.getByText(/^Library: /)).toBeVisible();
});

test("the language choice survives a reload", async ({ page }) => {
  await openApp(page, "/settings/general");
  await page.getByRole("radio", { name: "Türkçe" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Genel" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Genel" })).toBeVisible();

  await page.getByRole("radio", { name: "English" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "General" })).toBeVisible();
});

test("a backup runs in the worker and is listed", async ({ page }) => {
  await openApp(page, "/settings/backup");

  await page.getByRole("button", { name: "Back up now" }).click();

  await expect(page.getByText("Backup written.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("cell", { name: /^TEz-backup-.*\.zip$/ })).toBeVisible();
});
