// Server-Sent Events over fetch. The browser's EventSource cannot send the Authorization
// header the API requires, so the stream is read and parsed here (WHATWG SSE format).

export interface SseMessage {
  event: string;
  data: string;
  id: string | undefined;
}

/** Parse an SSE byte stream into messages. Comments (": ping") are skipped. */
export async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  let data: string[] = [];
  let id: string | undefined;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      let newline: number;
      while ((newline = buffer.search(/\r\n|\r|\n/)) >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + (buffer.startsWith("\r\n", newline) ? 2 : 1));
        if (line === "") {
          if (data.length > 0) yield { event: event || "message", data: data.join("\n"), id };
          event = "";
          data = [];
          continue;
        }
        if (line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        const raw = colon < 0 ? "" : line.slice(colon + 1);
        const content = raw.startsWith(" ") ? raw.slice(1) : raw;
        if (field === "event") event = content;
        else if (field === "data") data.push(content);
        else if (field === "id") id = content;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
