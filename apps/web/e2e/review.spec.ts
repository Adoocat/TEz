// Task 24: a review made through the wizard is PRISMA 2020, and its panel counts come from
// the records actually in the review.
import { expect, test } from "@playwright/test";

import { backend, openApp } from "./helpers";

test("a new review is PRISMA 2020 and its panel counts its records", async ({ page, request }) => {
  const title = `E2E review ${String(Date.now())}`;
  await openApp(page, "/review");

  await page.getByRole("button", { name: "New review" }).click();
  const dialog = page.getByRole("dialog", { name: "New review" });
  await dialog.getByRole("textbox", { name: "Title" }).fill(title);
  await expect(dialog.getByRole("radio", { name: "PRISMA 2020" })).toBeChecked();
  await dialog.getByRole("button", { name: "Next" }).click();
  await dialog.getByRole("textbox", { name: "Research question 1" }).fill("Which methods?");
  await dialog.getByRole("button", { name: "Create review" }).click();

  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await expect(page.getByText("PRISMA 2020", { exact: true })).toBeVisible();
  await expect(page.getByText("Which methods?")).toBeVisible();
  const stages = page.getByRole("region", { name: "Stages" });
  await expect(stages.getByText("0 records in the review")).toBeVisible();

  // Two records enter the review through an import; nothing else is told about them.
  const { api, headers } = backend();
  const reviews = (await (await request.get(`${api}/reviews`, { headers })).json()) as {
    id: string;
    title: string;
  }[];
  const reviewId = reviews.find((review) => review.title === title)?.id;
  const ris = ["Panel paper one", "Panel paper two"]
    .map((paperTitle) => `TY  - JOUR\nTI  - ${paperTitle} ${title}\nPY  - 2024\nER  - \n`)
    .join("\n");
  const imported = await request.post(`${api}/imports`, {
    headers,
    data: {
      file_name: "panel.ris",
      content_base64: Buffer.from(ris, "utf8").toString("base64"),
      review_id: reviewId,
      add_to_review: true,
    },
  });
  expect(imported.ok()).toBe(true);

  await page.reload();
  await expect(stages.getByText("2 records in the review")).toBeVisible();
  await expect(stages.getByText("2 waiting")).toBeVisible();
  await expect(
    stages.getByRole("link", { name: "Continue Title-abstract screening" }),
  ).toBeVisible();
});
