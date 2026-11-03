// Virtualized pdf.js viewer: every page gets a sized placeholder; only pages
// near the viewport get a canvas + text layer, far pages are torn down.
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "pdfjs-dist/web/pdf_viewer.css";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const SCALE = 1.25;
const KEEP_MARGIN_PX = 1500;

type Rendered = { canvas: HTMLCanvasElement; text: HTMLDivElement; task: pdfjs.RenderTask };

export type Viewer = {
  root: HTMLElement;
  doc: pdfjs.PDFDocumentProxy;
  pages: HTMLDivElement[];
  rendered: Map<number, Rendered>;
  renderTimes: number[];
  pendingRenders: Set<number>;
  stats: Record<string, number>;
};

function heapMb(): number {
  const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
  return mem ? Math.round(mem.usedJSHeapSize / 1048576) : -1;
}

export async function openPdf(root: HTMLElement, url: string, token: string): Promise<Viewer> {
  const t0 = performance.now();
  const doc = await pdfjs.getDocument({
    url,
    httpHeaders: { Authorization: `Bearer ${token}` },
    disableAutoFetch: true,
    rangeChunkSize: 65536,
  }).promise;
  const tDoc = performance.now();
  const first = await doc.getPage(1);
  const vp = first.getViewport({ scale: SCALE });

  root.replaceChildren();
  root.style.setProperty("--scale-factor", String(SCALE));
  root.style.setProperty("--total-scale-factor", String(SCALE));
  const pages: HTMLDivElement[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const div = document.createElement("div");
    div.className = "page";
    div.dataset.page = String(i);
    div.style.width = `${vp.width}px`;
    div.style.height = `${vp.height}px`;
    const label = document.createElement("span");
    label.className = "label";
    label.textContent = `s.${i}`;
    div.appendChild(label);
    root.appendChild(div);
    pages.push(div);
  }

  const viewer: Viewer = {
    root,
    doc,
    pages,
    rendered: new Map(),
    renderTimes: [],
    pendingRenders: new Set(),
    stats: { numPages: doc.numPages, docOpenMs: Math.round(tDoc - t0), firstPageMs: 0, heapAfterOpenMb: 0 },
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        const n = Number((e.target as HTMLElement).dataset.page);
        if (e.isIntersecting) void renderPage(viewer, n);
        else teardown(viewer, n);
      }
    },
    { root, rootMargin: `${KEEP_MARGIN_PX}px 0px` },
  );
  pages.forEach((p) => io.observe(p));

  await waitFor(() => viewer.rendered.has(1) && !viewer.pendingRenders.has(1));
  viewer.stats.firstPageMs = Math.round(performance.now() - t0);
  viewer.stats.heapAfterOpenMb = heapMb();
  return viewer;
}

async function renderPage(v: Viewer, n: number) {
  if (v.rendered.has(n) || v.pendingRenders.has(n)) return;
  v.pendingRenders.add(n);
  const t0 = performance.now();
  const page = await v.doc.getPage(n);
  const vp = page.getViewport({ scale: SCALE });
  const dpr = window.devicePixelRatio || 1;
  const canvas = document.createElement("canvas");
  canvas.width = Math.floor(vp.width * dpr);
  canvas.height = Math.floor(vp.height * dpr);
  canvas.style.width = `${vp.width}px`;
  canvas.style.height = `${vp.height}px`;
  const text = document.createElement("div");
  text.className = "textLayer";
  const host = v.pages[n - 1];
  host.append(canvas, text);
  const task = page.render({
    canvas,
    canvasContext: canvas.getContext("2d")!,
    viewport: vp,
    transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
  });
  v.rendered.set(n, { canvas, text, task });
  try {
    await task.promise;
    const tl = new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: text, viewport: vp });
    await tl.render();
    v.renderTimes.push(performance.now() - t0);
  } catch (err) {
    if (!(err instanceof pdfjs.RenderingCancelledException)) console.error(`page ${n}`, err);
  } finally {
    v.pendingRenders.delete(n);
  }
}

function teardown(v: Viewer, n: number) {
  const r = v.rendered.get(n);
  if (!r) return;
  r.task.cancel();
  r.canvas.width = 0; // release the backing store immediately
  r.canvas.remove();
  r.text.remove();
  v.rendered.delete(n);
  void v.doc.getPage(n).then((p) => p.cleanup());
}

function waitFor(cond: () => boolean, timeoutMs = 30000): Promise<void> {
  const t0 = performance.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (cond()) resolve();
      else if (performance.now() - t0 > timeoutMs) reject(new Error("timeout"));
      else requestAnimationFrame(tick);
    };
    tick();
  });
}

function percentile(xs: number[], p: number): number {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))];
}

/** Smooth-scroll pages 1→80 at a reading-like speed, then jump around. */
export async function scrollBenchmark(v: Viewer) {
  const root = v.root;
  root.scrollTop = 0;
  const pageH = v.pages[1].offsetTop - v.pages[0].offsetTop;
  const target = pageH * 80;
  const speed = 3000; // px/s, a fast skim
  const frames: number[] = [];
  let maxRendered = 0;

  await new Promise<void>((resolve) => {
    let last = performance.now();
    const t0 = last;
    const step = (now: number) => {
      frames.push(now - last);
      last = now;
      root.scrollTop = Math.min(target, ((now - t0) / 1000) * speed);
      maxRendered = Math.max(maxRendered, v.rendered.size);
      if (root.scrollTop >= target) resolve();
      else requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });

  const jumps: Record<string, number> = {};
  for (const n of [150, 300, 1]) {
    const t0 = performance.now();
    v.pages[n - 1].scrollIntoView({ block: "start" });
    await waitFor(() => v.rendered.has(n) && !v.pendingRenders.has(n));
    jumps[`jumpToPage${n}Ms`] = Math.round(performance.now() - t0);
  }

  const total = frames.reduce((a, b) => a + b, 0);
  return {
    scrolledPages: 80,
    scrollSeconds: +(total / 1000).toFixed(1),
    avgFps: +(frames.length / (total / 1000)).toFixed(1),
    p95FrameMs: +percentile(frames, 95).toFixed(1),
    longFrames50ms: frames.filter((f) => f > 50).length,
    maxPagesInDom: maxRendered,
    renderedPagesTotal: v.renderTimes.length,
    avgPageRenderMs: Math.round(v.renderTimes.reduce((a, b) => a + b, 0) / Math.max(1, v.renderTimes.length)),
    p95PageRenderMs: Math.round(percentile(v.renderTimes, 95)),
    ...jumps,
    heapAfterBenchMb: heapMb(),
  };
}
