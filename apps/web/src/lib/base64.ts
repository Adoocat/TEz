/** A file's bytes as base64, for JSON request bodies. The server decodes the text itself. */
export async function fileToBase64(file: Blob): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  // In chunks: spreading a whole large file into fromCharCode overflows the call stack.
  const chunk = 0x8000;
  let binary = "";
  for (let start = 0; start < bytes.length; start += chunk) {
    binary += String.fromCharCode(...bytes.subarray(start, start + chunk));
  }
  return btoa(binary);
}
