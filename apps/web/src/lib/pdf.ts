// pdf.js behind a small interface. Loaded on first use, so the reader's ~1 MB is not part of
// the start-up bundle, and component tests can stand in a fake.
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

export interface PdfPageSize {
  width: number;
  height: number;
}

export interface RenderedPage {
  /** Stops a render in flight and frees the page's resources. */
  dispose: () => void;
  done: Promise<void>;
}

export interface OutlineItem {
  title: string;
  /** Counts from 1; null when the entry points nowhere we can open. */
  page: number | null;
  children: OutlineItem[];
}

export interface PdfDocument {
  numPages: number;
  /** Size at scale 1, in CSS pixels (PDF points). */
  pageSize: (pageNumber: number) => Promise<PdfPageSize>;
  /** Draws a page into `canvas` and lays its selectable text into `textLayer`. */
  renderPage: (
    pageNumber: number,
    target: { canvas: HTMLCanvasElement; textLayer: HTMLElement; scale: number },
  ) => RenderedPage;
  /** Draws a page `width` CSS pixels wide, without text. */
  renderThumbnail: (pageNumber: number, canvas: HTMLCanvasElement, width: number) => RenderedPage;
  /** The document's own table of contents; empty when it has none. */
  outline: () => Promise<OutlineItem[]>;
  destroy: () => Promise<void>;
}

export interface OpenOptions {
  url: string;
  /** Sent with every range request: the API token. */
  headers: Record<string, string>;
}

export type PdfOpener = (options: OpenOptions) => Promise<PdfDocument>;

/** pdf.js's data files, served by the `pdfjsAssets` plugin (vite.config.ts): fonts for PDFs
 * that embed none, decoders for JPEG 2000 and JBIG2 scans, CJK character maps. */
function asset(folder: string): string {
  return new URL(`${import.meta.env.BASE_URL}pdfjs/${folder}/`, window.location.href).href;
}

// Ranges of 256 kB: a page or two of a typical paper per request.
const RANGE_CHUNK = 256 * 1024;

async function loadPdfJs() {
  const [pdfjs, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  return pdfjs;
}

export const openPdf: PdfOpener = async ({ url, headers }) => {
  const pdfjs = await loadPdfJs();
  const loading = pdfjs.getDocument({
    url,
    httpHeaders: headers,
    rangeChunkSize: RANGE_CHUNK,
    // Fetch only what is shown: a 300-page scan is never downloaded whole.
    disableAutoFetch: true,
    disableStream: true,
    standardFontDataUrl: asset("standard_fonts"),
    wasmUrl: asset("wasm"),
    iccUrl: asset("iccs"),
    cMapUrl: asset("cmaps"),
    cMapPacked: true,
  });
  const document: PDFDocumentProxy = await loading.promise;

  return {
    numPages: document.numPages,
    async pageSize(pageNumber) {
      const page = await document.getPage(pageNumber);
      const viewport = page.getViewport({ scale: 1 });
      return { width: viewport.width, height: viewport.height };
    },
    renderPage(pageNumber, { canvas, textLayer, scale }) {
      // An object, not a plain flag: the async body reads it after awaits.
      const state = { cancelled: false };
      let page: PDFPageProxy | null = null;
      let renderTask: { cancel: () => void } | null = null;
      let text: { cancel: () => void } | null = null;
      const done = (async () => {
        page = await document.getPage(pageNumber);
        if (state.cancelled) return;
        const viewport = page.getViewport({ scale });
        const ratio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * ratio);
        canvas.height = Math.floor(viewport.height * ratio);
        canvas.style.width = `${String(Math.floor(viewport.width))}px`;
        canvas.style.height = `${String(Math.floor(viewport.height))}px`;
        const task = page.render({
          canvas,
          viewport,
          transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0],
        });
        renderTask = task;
        textLayer.replaceChildren();
        textLayer.removeAttribute("data-main-rotation");
        textLayer.style.setProperty("--total-scale-factor", String(scale));
        const layer = new pdfjs.TextLayer({
          textContentSource: page.streamTextContent(),
          container: textLayer,
          viewport,
        });
        text = layer;
        await Promise.all([task.promise, layer.render()]);
      })().catch((error: unknown) => {
        // A cancelled render rejects; that is the point of cancelling, not a failure.
        if (state.cancelled) return;
        throw error;
      });
      return {
        done,
        dispose() {
          state.cancelled = true;
          renderTask?.cancel();
          text?.cancel();
          page?.cleanup();
        },
      };
    },
    renderThumbnail(pageNumber, canvas, width) {
      const state = { cancelled: false };
      let renderTask: { cancel: () => void } | null = null;
      const done = (async () => {
        const page = await document.getPage(pageNumber);
        if (state.cancelled) return;
        const ratio = window.devicePixelRatio || 1;
        const viewport = page.getViewport({
          scale: (width * ratio) / page.getViewport({ scale: 1 }).width,
        });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        const task = page.render({ canvas, viewport });
        renderTask = task;
        await task.promise;
      })().catch((error: unknown) => {
        if (state.cancelled) return;
        throw error;
      });
      return {
        done,
        dispose() {
          state.cancelled = true;
          renderTask?.cancel();
        },
      };
    },
    async outline() {
      return readOutline(document, await document.getOutline());
    },
    destroy: () => loading.destroy(),
  };
};

type RawOutline = Awaited<ReturnType<PDFDocumentProxy["getOutline"]>>;

async function readOutline(document: PDFDocumentProxy, items: RawOutline): Promise<OutlineItem[]> {
  return Promise.all(
    // pdf.js types the list as never null; a document without an outline gives null.
    ((items as RawOutline | null) ?? []).map(async (item) => ({
      title: item.title.trim(),
      page: await destinationPage(document, item.dest).catch(() => null),
      children: await readOutline(document, item.items as RawOutline),
    })),
  );
}

/** The page a destination points at; null for links out of the document and broken ones. */
async function destinationPage(
  document: PDFDocumentProxy,
  dest: string | unknown[] | null,
): Promise<number | null> {
  const explicit = typeof dest === "string" ? await document.getDestination(dest) : dest;
  const target: unknown = explicit?.[0];
  if (typeof target === "number") return target + 1;
  if (typeof target !== "object" || target === null) return null;
  return (await document.getPageIndex(target as { num: number; gen: number })) + 1;
}
