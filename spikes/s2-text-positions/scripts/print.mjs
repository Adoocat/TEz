// Chromium's own PDF writer (Skia) for the HTML samples.
import { readdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const here = import.meta.dirname;
const out = path.join(here, "..", "out");
const require = createRequire(path.join(here, "../../../apps/web/package.json"));
const { chromium } = require("@playwright/test");

const browser = await chromium.launch();
const page = await browser.newPage();
for (const name of readdirSync(out).filter((n) => n.endsWith(".html"))) {
  await page.goto(pathToFileURL(path.join(out, name)).href);
  await page.pdf({ path: path.join(out, name.replace(".html", ".pdf")), format: "A4" });
}
await browser.close();
