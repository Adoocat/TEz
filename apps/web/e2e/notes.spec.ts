// Task 49 acceptance, end to end: write a note with links in the real editor; nothing is lost
// when the window closes.
import { expect, test } from "@playwright/test";

import { addPdf, importPapers, makePdf, openApp } from "./helpers";

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

test("a quote goes from the reader to a note, and its chip leads back to the sentence", async ({
  page,
  request,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const attachmentId = await addPdf(request, "avocet.pdf", makePdf(6, "Avocet feeding grounds"));
  await openApp(page, `/reader/${attachmentId}?page=4`);
  const reader = page.getByRole("document", { name: "avocet.pdf" });
  const line = reader
    .getByRole("region", { name: "Page 4", exact: true })
    .getByText("Avocet feeding grounds page 4", { exact: true });
  const selectLine = async () => {
    await expect(line).toBeVisible();
    const box = await line.boundingBox();
    if (!box) throw new Error("no box");
    await page.mouse.move(box.x + 1, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width - 1, box.y + box.height / 2, { steps: 8 });
    await page.mouse.up();
    await expect(page.getByRole("toolbar", { name: "Selected text" })).toBeVisible();
  };

  // With the keyboard, into a new note.
  await selectLine();
  await page.keyboard.press("Shift+N");
  const dialog = page.getByRole("dialog", { name: "Quote in a note" });
  await dialog.getByRole("button", { name: "New note about this paper" }).click();
  await expect(page.getByText("Quoted in avocet.")).toBeVisible();

  // With the mouse, into the same note, and to the clipboard.
  await selectLine();
  await page
    .getByRole("toolbar", { name: "Selected text" })
    .getByRole("button", { name: "Copy with source" })
    .click();
  await expect(page.getByText("Copied with its source.")).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(
    "\u201cAvocet feeding grounds page 4\u201d (avocet, p. 4)",
  );
  await page.getByRole("radio", { name: "Notes" }).click();
  await page
    .getByRole("region", { name: "Notes about this paper" })
    .getByRole("link", { name: "avocet" })
    .click();

  // The note has the words and a chip; the chip opens the reader at the sentence.
  const preview = page.getByRole("article", { name: "Preview" });
  await expect(preview.getByRole("blockquote")).toContainText("Avocet feeding grounds page 4");
  await preview.getByRole("link", { name: "avocet, p. 4" }).click();
  const flash = reader.getByTestId("anchor-flash");
  await expect(flash).toBeVisible();
  const [a, b] = [await flash.boundingBox(), await line.boundingBox()];
  if (!a || !b) throw new Error("no box");
  expect(Math.abs(a.x - b.x)).toBeLessThan(6);
  expect(Math.abs(a.y + a.height / 2 - (b.y + b.height / 2))).toBeLessThan(10);
});
