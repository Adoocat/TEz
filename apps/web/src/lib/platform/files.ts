// Clipboard and saving files the app made. The browser and the desktop webviews (WebView2,
// WKWebView, WebKitGTK) share these web APIs, so both platforms use this module.
import { saveBlob } from "@/lib/download";

export async function copyToClipboard(text: string, html?: string): Promise<void> {
  if (html !== undefined && typeof ClipboardItem !== "undefined") {
    // Both flavours: Word and other editors take the formatted one, plain editors the text.
    await navigator.clipboard.write([
      new ClipboardItem({
        "text/plain": new Blob([text], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      }),
    ]);
    return;
  }
  await navigator.clipboard.writeText(text);
}

export function saveTextFile(fileName: string, content: string, mimeType: string): Promise<void> {
  saveBlob(fileName, new Blob([content], { type: `${mimeType};charset=utf-8` }));
  return Promise.resolve();
}
