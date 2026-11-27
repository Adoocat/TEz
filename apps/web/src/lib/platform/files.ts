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

export function saveTextFile(
  fileName: string,
  content: string | Uint8Array,
  mimeType: string,
): Promise<void> {
  const blob =
    typeof content === "string"
      ? new Blob([content], { type: `${mimeType};charset=utf-8` })
      : new Blob([new Uint8Array(content)], { type: mimeType });
  saveBlob(fileName, blob);
  return Promise.resolve();
}
