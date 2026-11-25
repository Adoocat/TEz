// Task 18 acceptance, end to end: organize papers with collections, tags and reading status
// against the real backend.
import { expect, test } from "@playwright/test";

import { addPdf, importPapers, makePdf, openApp } from "./helpers";

const FIRST = "Automated Code Review with Large Language Models";
const SECOND = "Reviewer Recommendation in Practice";

test("collections, tags and reading status organize the library", async ({ page, request }) => {
  await importPapers(request, [FIRST, SECOND]);
  await openApp(page);

  const sidebar = page.getByRole("navigation", { name: "Library" });
  const papers = page.getByRole("table", { name: "Papers" });
  await expect(page.getByRole("heading", { level: 1, name: "All papers" })).toBeVisible();
  await expect(papers.getByText(FIRST)).toBeVisible();

  // A collection, and one inside it.
  await sidebar.getByRole("button", { name: "New collection" }).click();
  await page.getByRole("textbox", { name: "Collection name" }).fill("Tez");
  await page.keyboard.press("Enter");
  await expect(sidebar.getByRole("button", { name: "Tez", exact: true })).toBeVisible();
  await sidebar.getByRole("button", { name: "Tez", exact: true }).hover();
  await sidebar.getByRole("button", { name: "New collection inside Tez" }).click();
  await page.getByRole("textbox", { name: "Collection name" }).fill("Yöntem");
  await page.keyboard.press("Enter");
  const method = sidebar.getByRole("button", { name: "Yöntem", exact: true });
  await expect(method).toBeVisible();

  // Drag a paper onto the sub-collection.
  await papers.getByRole("row").filter({ hasText: FIRST }).dragTo(method);
  await method.click();
  await expect(page.getByRole("heading", { level: 1, name: "Yöntem" })).toBeVisible();
  await expect(papers.getByText(FIRST)).toBeVisible();
  await expect(papers.getByText(SECOND)).toHaveCount(0);

  // A tag, given to the paper through the bulk bar.
  await sidebar.getByRole("button", { name: "New tag" }).click();
  await page.getByRole("textbox", { name: "Tag name" }).fill("anket");
  await page.keyboard.press("Enter");
  await expect(sidebar.getByRole("button", { name: "#anket" })).toBeVisible();
  await page.getByRole("checkbox", { name: `Select: ${FIRST}` }).check();
  await page.getByRole("combobox", { name: "Add tag…" }).selectOption({ label: "#anket" });
  await page.getByRole("combobox", { name: "Reading status…" }).selectOption({ label: "Reading" });
  await expect(papers.getByRole("img", { name: "Reading" })).toBeVisible();

  await sidebar.getByRole("button", { name: "#anket" }).click();
  await expect(papers.getByText(FIRST)).toBeVisible();
  await expect(papers.getByText(SECOND)).toHaveCount(0);

  // Renaming and deleting the parent collection keeps the papers.
  await sidebar.getByRole("button", { name: "Tez", exact: true }).hover();
  await sidebar.getByRole("button", { name: "Rename Tez" }).click();
  await page.getByRole("textbox", { name: "New name" }).fill("Tez çalışması");
  await page.keyboard.press("Enter");
  await expect(sidebar.getByRole("button", { name: "Tez çalışması", exact: true })).toBeVisible();
  await sidebar.getByRole("button", { name: "Tez çalışması", exact: true }).hover();
  await sidebar.getByRole("button", { name: "Delete Tez çalışması" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(sidebar.getByRole("button", { name: "Yöntem", exact: true })).toHaveCount(0);

  await sidebar.getByRole("button", { name: "All papers" }).click();
  await expect(papers.getByText(FIRST)).toBeVisible();
  await expect(papers.getByText(SECOND)).toBeVisible();
});

test("the library is searched by metadata, Turkish letters folded", async ({ page, request }) => {
  await importPapers(request, ["Işık Kaynaklarının Kod İncelemesine Etkisi"]);
  await openApp(page);
  const papers = page.getByRole("table", { name: "Papers" });
  await expect(papers.getByText(FIRST).first()).toBeVisible();

  await page.getByRole("searchbox", { name: "Search the library" }).fill("isik kod");

  await expect(papers.getByText("Işık Kaynaklarının Kod İncelemesine Etkisi")).toBeVisible();
  await expect(papers.getByText(FIRST)).toHaveCount(0);
  await papers.getByText("Işık Kaynaklarının Kod İncelemesine Etkisi").click();
  await expect(
    page.getByRole("complementary", { name: "Inspector" }).getByRole("heading", {
      name: "Işık Kaynaklarının Kod İncelemesine Etkisi",
    }),
  ).toBeVisible();
});

test("full-text search finds a passage and opens the reader on its page", async ({
  page,
  request,
}) => {
  await addPdf(request, "fulltext-paper.pdf", makePdf(4, "Ethnography zeppelin"));
  await openApp(page, "/library");
  await page.getByRole("radio", { name: "Full text" }).click();
  // The worker reads the PDF in the background.
  await expect(async () => {
    await page.getByRole("searchbox", { name: "Search the library" }).fill("");
    await page.getByRole("searchbox", { name: "Search the library" }).fill("zeppelin page 3");
    await expect(page.getByRole("link", { name: /p\. 3/ })).toBeVisible({ timeout: 1500 });
  }).toPass({ timeout: 45_000 });

  await page.getByRole("link", { name: /p\. 3/ }).click();

  const reader = page.getByRole("document", { name: "fulltext-paper.pdf" });
  await expect(reader.getByRole("region", { name: "Page 3" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Page" })).toHaveValue("3");
});
