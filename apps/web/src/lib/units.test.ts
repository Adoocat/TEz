// Unit tests for the small libraries behind the shell: SSE parsing, i18n files, platform
// detection, theme preferences.
import { afterEach, describe, expect, it, vi } from "vitest";

import en from "../../locales/en/common.json";
import tr from "../../locales/tr/common.json";
import { createI18n, errorMessage } from "@/i18n";

import { browserBackendState, takeConnectionFromUrl } from "./platform/browser";
import { fromShell } from "./platform/tauri";
import { applyTheme, cachedTheme, resolveTheme } from "./preferences";
import { parseSse, type SseMessage } from "./sse";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SseMessage[]> {
  const messages: SseMessage[] = [];
  for await (const message of parseSse(stream)) messages.push(message);
  return messages;
}

describe("parseSse", () => {
  it("parses events split across chunks, with ids, comments and CRLF", async () => {
    const messages = await collect(
      streamOf(
        ": ping\n\nevent: jo",
        'b\r\nid: 7\r\ndata: {"a":',
        "1}\r\n\r\n",
        "data: x\ndata: y\n\n",
      ),
    );

    expect(messages).toEqual([
      { event: "job", id: "7", data: '{"a":1}' },
      { event: "message", id: "7", data: "x\ny" },
    ]);
  });

  it("decodes UTF-8 split in the middle of a character", async () => {
    const bytes = new TextEncoder().encode("data: ışık\n\n");
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 7));
        controller.enqueue(bytes.slice(7));
        controller.close();
      },
    });

    expect((await collect(stream))[0]?.data).toBe("ışık");
  });
});

describe("translations", () => {
  const keys = (value: unknown, prefix = ""): string[] =>
    typeof value === "object" && value !== null
      ? Object.entries(value).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k))
      : [prefix];

  it("Turkish and English have the same keys", () => {
    expect(keys(tr).sort()).toEqual(keys(en).sort());
  });

  it("turn backend error codes into messages, with an unknown-code fallback", () => {
    const i18n = createI18n("tr");

    expect(errorMessage(i18n.t, { code: "library.not_found", params: { path: "C:/x" } })).toBe(
      "Kütüphane bulunamadı: C:/x",
    );
    expect(errorMessage(i18n.t, { code: "made.up" })).toBe("Beklenmeyen bir hata oluştu.");
  });
});

describe("platform", () => {
  afterEach(() => {
    sessionStorage.clear();
    window.history.replaceState(null, "", "/");
  });

  it("takes the API address and token from the URL fragment and removes them", () => {
    window.history.replaceState(null, "", "/?x=1#api=http://127.0.0.1:5000&token=abc");

    const state = browserBackendState(false);

    expect(state).toEqual({
      status: "ready",
      connection: { baseUrl: "http://127.0.0.1:5000", token: "abc" },
    });
    expect(window.location.href).not.toContain("abc");
    // A reload in the same tab still works.
    expect(browserBackendState(false)).toEqual(state);
  });

  it("uses the dev proxy in development and refuses without a token otherwise", () => {
    expect(browserBackendState(true)).toEqual({
      status: "ready",
      connection: { baseUrl: "/api", token: "" },
    });
    expect(browserBackendState(false)).toEqual({
      status: "failed",
      error: { code: "backend.no_token" },
    });
  });

  it("ignores a fragment without both parts", () => {
    window.history.replaceState(null, "", "/#token=abc");
    expect(takeConnectionFromUrl(window.location, window.history)).toBeNull();
  });

  it("maps the desktop shell's backend status", () => {
    expect(fromShell({ status: "ready", port: 5123, token: "t" })).toEqual({
      status: "ready",
      connection: { baseUrl: "http://127.0.0.1:5123", token: "t" },
    });
    expect(fromShell({ status: "failed", code: "library.locked", params: { pid: 1 } })).toEqual({
      status: "failed",
      error: { code: "library.locked", params: { pid: 1 } },
    });
  });
});

describe("theme", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("follows the operating system for 'system'", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("dark") }));

    expect(resolveTheme("system")).toBe("dark");
    expect(resolveTheme("light")).toBe("light");
  });

  it("caches an explicit choice for the next start, but not 'system'", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(cachedTheme()).toBe("dark");

    applyTheme("system");
    expect(cachedTheme()).toBe("system");
  });
});
