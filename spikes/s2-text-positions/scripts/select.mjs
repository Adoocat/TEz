// Select text in pdf.js's text layer, the way a reader would, and write down what was selected
// and where (PDF user space). Output: out/selections.json
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import path from "node:path";

const here = import.meta.dirname;
const out = path.join(here, "..", "out");
const web = path.join(here, "../../../apps/web");
const require = createRequire(path.join(web, "package.json"));
const { chromium } = require("@playwright/test");
const dist = path.join(web, "node_modules", "pdfjs-dist");

// The same text-layer rules the app uses.
const css = readFileSync(path.join(web, "src/styles/index.css"), "utf8");
const textLayerCss =
  css.slice(css.indexOf(".textLayer")) +
  // Missing from the app when this spike was written (rotated pages were misplaced).
  `.textLayer{--scale-round-x:1px;--scale-round-y:1px}
   [data-main-rotation="90"]{transform:rotate(90deg) translateY(-100%)}
   [data-main-rotation="180"]{transform:rotate(180deg) translate(-100%,-100%)}
   [data-main-rotation="270"]{transform:rotate(270deg) translateX(-100%)}`;

const server = http.createServer((req, res) => {
  const name = decodeURIComponent(req.url.split("?")[0]);
  try {
    if (name === "/") {
      res.setHeader("content-type", "text/html");
      res.end(
        `<!doctype html><meta charset=utf-8><style>${textLayerCss}</style>` +
          `<div id=page style="position:relative"><div id=layer class=textLayer></div></div>`,
      );
      return;
    }
    const file = name.startsWith("/pdfjs/")
      ? path.join(dist, name.slice("/pdfjs/".length))
      : path.join(out, name.slice(1));
    res.setHeader("content-type", file.endsWith("mjs") ? "text/javascript" : "application/pdf");
    res.end(readFileSync(file));
  } catch {
    res.statusCode = 404;
    res.end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch();
const page = await browser.newPage();
page.on("pageerror", (error) => console.error(error.message));
await page.goto(origin);
const all = [];
for (const name of readdirSync(out).filter((n) => n.endsWith(".pdf"))) {
  const found = await page.evaluate(
    async ({ name, perPage }) => {
      const pdfjs = await import("/pdfjs/build/pdf.mjs");
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/build/pdf.worker.mjs";
      const doc = await pdfjs.getDocument({ url: `/${name}` }).promise;
      const layer = document.getElementById("layer");
      const host = document.getElementById("page");
      // Deterministic choices, so a run can be repeated.
      let seed = 7;
      const random = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
      const results = [];
      for (let n = 1; n <= doc.numPages; n++) {
        const pdfPage = await doc.getPage(n);
        const viewport = pdfPage.getViewport({ scale: 1.4 });
        host.style.width = `${viewport.width}px`;
        host.style.height = `${viewport.height}px`;
        layer.replaceChildren();
        layer.removeAttribute("data-main-rotation");
        layer.style.setProperty("--total-scale-factor", "1.4");
        await new pdfjs.TextLayer({
          textContentSource: pdfPage.streamTextContent(),
          container: layer,
          viewport,
        }).render();
        const nodes = [];
        const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          if (walker.currentNode.data.trim()) nodes.push(walker.currentNode);
        }
        for (let i = 0; i < perPage; i++) {
          const first = Math.floor(random() * nodes.length);
          const last = Math.min(nodes.length - 1, first + Math.floor(random() * 4));
          const from = Math.floor(random() * Math.max(1, nodes[first].length - 8));
          const range = document.createRange();
          range.setStart(nodes[first], first === last ? 0 : from);
          range.setEnd(
            nodes[last],
            first === last
              ? nodes[last].length
              : Math.max(1, Math.floor(random() * nodes[last].length)),
          );
          const selection = getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          const text = selection.toString();
          if (text.replace(/[^\p{L}\p{N}]/gu, "").length < 8) continue;
          const box = host.getBoundingClientRect();
          const rects = [...range.getClientRects()]
            .filter((r) => r.width > 0.5 && r.height > 0.5)
            .map((r) => {
              const a = viewport.convertToPdfPoint(r.left - box.left, r.top - box.top);
              const b = viewport.convertToPdfPoint(r.right - box.left, r.bottom - box.top);
              return [
                Math.min(a[0], b[0]),
                Math.min(a[1], b[1]),
                Math.max(a[0], b[0]),
                Math.max(a[1], b[1]),
              ];
            });
          results.push({ file: name, page: n - 1, text, rects });
        }
      }
      return results;
    },
    { name, perPage: 60 },
  );
  console.log(name, found.length);
  all.push(...found);
}
writeFileSync(path.join(out, "selections.json"), JSON.stringify(all));
await browser.close();
server.close();
