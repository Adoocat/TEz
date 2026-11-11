import type { APIRequestContext, Page } from "@playwright/test";

export function backend() {
  const api = process.env.TEZ_E2E_API;
  const token = process.env.TEZ_E2E_TOKEN;
  if (!api || !token) throw new Error("the e2e backend is not running (global setup)");
  return { api, token, headers: { Authorization: `Bearer ${token}` } };
}

/** Opens the app the way `tez serve`'s link does: address and token in the fragment. */
export async function openApp(page: Page, route = "/library") {
  const { api, token } = backend();
  await page.goto(`/#api=${encodeURIComponent(api)}&token=${encodeURIComponent(token)}`);
  await page.evaluate((hash) => {
    window.location.hash = hash;
  }, route);
}

/** Puts papers in the library through the import API, as a user's RIS file would. */
export async function importPapers(request: APIRequestContext, titles: string[]) {
  const { api, headers } = backend();
  const ris = titles
    .map((title, index) =>
      [
        "TY  - JOUR",
        `TI  - ${title}`,
        "AU  - Yılmaz, Ayşe",
        `PY  - ${String(2020 + index)}`,
        `DO  - 10.5555/e2e.${String(Date.now())}.${String(index)}`,
        "ER  - ",
        "",
      ].join("\n"),
    )
    .join("\n");
  const response = await request.post(`${api}/imports`, {
    headers,
    data: {
      file_name: "e2e.ris",
      content_base64: Buffer.from(ris, "utf8").toString("base64"),
      add_to_library: true,
    },
  });
  if (!response.ok()) throw new Error(`import failed: ${await response.text()}`);
}
