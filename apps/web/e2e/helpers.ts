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

const NL = "\n";

/**
 * A valid PDF of `pages` pages with a line of text each, written by hand (no fixtures). Pages
 * hang from a balanced tree of ten per node, its nodes written together as real producers do:
 * a reader then finds any page after reading a few small parts of the file.
 */
export function makePdf(pages: number, label = "TEz e2e", padding = 0): Buffer {
  const objects: string[] = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  const groupCount = Math.ceil(pages / 10);
  const firstGroup = objects.length + 1;
  const groups: number[][] = [];
  for (let group = 0; group < groupCount; group += 1) {
    objects.push("");
    groups.push([]);
  }
  for (let index = 0; index < pages; index += 1) {
    const group = Math.floor(index / 10);
    const text = `${label} page ${String(index + 1)}`;
    // `padding` bytes of comment make a file as heavy as a real one without drawing more.
    const filler = padding > 0 ? `% ${"x".repeat(padding)}${NL}` : "";
    const stream = `${filler}BT /F1 24 Tf 72 720 Td (${text}) Tj ET`;
    objects.push(`<< /Length ${String(stream.length)} >>${NL}stream${NL}${stream}${NL}endstream`);
    const content = objects.length;
    objects.push(
      `<< /Type /Page /Parent ${String(firstGroup + group)} 0 R /MediaBox [0 0 612 792] ` +
        `/Resources << /Font << /F1 3 0 R >> >> /Contents ${String(content)} 0 R >>`,
    );
    groups[group]?.push(objects.length);
  }
  const ref = (n: number) => `${String(n)} 0 R`;
  groups.forEach((kids, group) => {
    objects[firstGroup + group - 1] =
      `<< /Type /Pages /Parent 2 0 R /Kids [${kids.map(ref).join(" ")}] ` +
      `/Count ${String(kids.length)} >>`;
  });
  objects[1] =
    `<< /Type /Pages /Kids [${groups.map((_, group) => ref(firstGroup + group)).join(" ")}] ` +
    `/Count ${String(pages)} >>`;
  let out = `%PDF-1.4${NL}`;
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(Buffer.byteLength(out));
    out += `${String(index + 1)} 0 obj${NL}${body}${NL}endobj${NL}`;
  });
  const xref = Buffer.byteLength(out);
  out += `xref${NL}0 ${String(objects.length + 1)}${NL}0000000000 65535 f ${NL}`;
  out += offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n ${NL}`).join("");
  out += `trailer${NL}<< /Size ${String(objects.length + 1)} /Root 1 0 R >>${NL}`;
  out += `startxref${NL}${String(xref)}${NL}%%EOF${NL}`;
  return Buffer.from(out, "latin1");
}

/** Adds a PDF through the API, as a drop would; returns its attachment id. */
export async function addPdf(request: APIRequestContext, name: string, data: Buffer) {
  const { api, headers } = backend();
  const response = await request.post(`${api}/pdfs?file_name=${encodeURIComponent(name)}`, {
    headers: { ...headers, "Content-Type": "application/pdf" },
    data,
  });
  if (!response.ok()) throw new Error(`pdf upload failed: ${await response.text()}`);
  return ((await response.json()) as { attachment_id: string }).attachment_id;
}
