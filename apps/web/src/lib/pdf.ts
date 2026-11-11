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

export interface PdfDocument {
  numPages: number;
  /** Size at scale 1, in CSS pixels (PDF points). */
  pageSize: (pageNumber: number) => Promise<PdfPageSize>;
  /** Draws a page into `canvas` and lays its selectable text into `textLayer`. */
  renderPage: (
    pageNumber: number,
    target: { canvas: HTMLCanvasElement; textLayer: HTMLElement; scale: number },
  ) => RenderedPage;
  destroy: () => Promise<void>;
}

export interface OpenOptions {
  url: string;
  /** Sent with every range request: the API token. */
  headers: Record<string, string>;
}

export type PdfOpener = (options: OpenOptions) => Promise<PdfDocument>;

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
    destroy: () => loading.destroy(),
  };
};
