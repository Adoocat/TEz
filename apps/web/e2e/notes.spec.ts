// Task 49 acceptance, end to end: write a note with links in the real editor; nothing is lost
// when the window closes.
import { expect, test } from "@playwright/test";

import { importPapers, openApp } from "./helpers";

const PAPER = "Listening to Wetland Birds at Night";

test("notes: write, link with [[, backlinks, rename, search", async ({ page, request }) => {
  await importPapers(request, [PAPER]);
  await openApp(page, "/notes");

  await page.getByRole("button", { name: "New note", exact: true }).click();
  const title = page.getByRole("textbox", { name: "Note title" });
  await expect(title).toHaveValue("Untitled note");
  await title.fill("Wetland method");
  const editor = page.getByRole("textbox", { name: "Note text" });
  await editor.click();
  await page.keyboard.type("## Recording\n\nAs in [[wetland birds");
  const option = page.getByRole("option", { name: new RegExp(PAPER) });
  await expect(option).toBeVisible();
  await page.keyboard.press("Enter");
  await page.keyboard.type(", and later [[Bittern calls");
  await page.getByRole("option", { name: "New note: Bittern calls" }).click();
  await page.keyboard.type(".");

  const preview = page.getByRole("article", { name: "Preview" });
  await expect(preview.getByRole("heading", { name: "Recording" })).toBeVisible();
  await expect(preview.getByRole("link", { name: /20\d\d/ })).toHaveAttribute("data-type", "paper");
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();

  // The new note knows who links to it.
  const tree = page.getByRole("list", { name: "Note tree" });
  await tree.getByRole("link", { name: "Bittern calls" }).click();
  await expect(title).toHaveValue("Bittern calls");
  const inspector = page.getByRole("complementary", { name: "Inspector" });
  await expect(inspector.getByRole("link", { name: "Wetland method" })).toBeVisible();

  // Renaming it keeps the link.
  await title.fill("Calls of the bittern");
  await expect(tree.getByRole("link", { name: "Calls of the bittern" })).toBeVisible();
  await tree.getByRole("link", { name: "Wetland method" }).click();
  await expect(preview.getByRole("link", { name: "Calls of the bittern" })).toBeVisible();
  // In the editor too: a chip, until the cursor is in it.
  await expect(
    page.getByTestId("note-editor").locator(".note-chip", { hasText: "Calls of the bittern" }),
  ).toBeVisible();

  await page.getByRole("searchbox", { name: "Search notes" }).fill("recording birds");
  await expect(page.getByText("No note has all of these words.")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search notes" }).fill("RECORD");
  await expect(
    page.getByRole("list", { name: "Notes found" }).getByRole("link", { name: /Wetland method/ }),
  ).toBeVisible();
});

test("text typed a moment before the window closes is there again", async ({ page, context }) => {
  await openApp(page, "/notes");
  await page.getByRole("button", { name: "New note", exact: true }).click();
  await page.getByRole("textbox", { name: "Note title" }).fill("Short notice");
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  // From here on no save gets through, as if the backend went away.
  await context.route("**/notes/*", (route) =>
    route.request().method() === "PATCH" ? route.abort() : route.continue(),
  );
  await page.getByRole("textbox", { name: "Note text" }).click();
  await page.keyboard.type("The last sentence.");
  await page.close();
  await context.unrouteAll();

  const again = await context.newPage();
  await openApp(again, "/notes");
  await again.getByRole("link", { name: "Short notice" }).click();

  await expect(again.getByRole("textbox", { name: "Note text" })).toContainText(
    "The last sentence.",
  );
  await expect(again.getByText("Saved", { exact: true })).toBeVisible();
  await again.reload();
  await openApp(again, "/notes");
  await again.getByRole("link", { name: "Short notice" }).click();
  await expect(again.getByRole("article", { name: "Preview" })).toContainText("The last sentence.");
});
