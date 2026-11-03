// An in-memory stand-in for the backend API, for component tests (no network).
import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";
import type { BackendState, Platform } from "@/lib/platform";

type AppSettings = components["schemas"]["AppSettings"];
type JobView = components["schemas"]["JobView"];

export interface FakeBackend {
  fetch: FetchLike;
  settings: AppSettings;
  secrets: Map<string, string>;
  requests: { method: string; path: string; body: unknown }[];
  /** Push a job update to every open /jobs/events stream. */
  emitJob: (job: JobView) => void;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function fakeBackend(initial: Partial<AppSettings> = {}): FakeBackend {
  const streams = new Set<ReadableStreamDefaultController<Uint8Array>>();
  const encoder = new TextEncoder();
  let eventId = 0;

  const backend: FakeBackend = {
    settings: { language: null, theme: "system", sources_email: null, ...initial },
    secrets: new Map(),
    requests: [],
    emitJob(job) {
      eventId += 1;
      const chunk = encoder.encode(
        `event: job\nid: ${String(eventId)}\ndata: ${JSON.stringify(job)}\n\n`,
      );
      for (const stream of streams) stream.enqueue(chunk);
    },
    async fetch(request) {
      const path = new URL(request.url, "http://test").pathname;
      const body: unknown =
        request.method === "GET" || request.method === "DELETE" ? undefined : await request.json();
      backend.requests.push({ method: request.method, path, body });

      const route = `${request.method} ${path}`;
      if (route === "GET /settings") return json(backend.settings);
      if (route === "PATCH /settings") {
        backend.settings = { ...backend.settings, ...(body as Partial<AppSettings>) };
        return json(backend.settings);
      }
      if (route === "GET /library") {
        return json({ path: "C:/TEz Library", name: "TEz Library", schema_revision: "0002" });
      }
      if (route === "GET /secrets") {
        return json(
          ["semantic_scholar_api_key", "openalex_api_key"].map((name) => ({
            name,
            configured: backend.secrets.has(name),
          })),
        );
      }
      const secret = /^\/secrets\/(.+)$/.exec(path)?.[1];
      if (secret && request.method === "PUT") {
        backend.secrets.set(secret, (body as { value: string }).value.trim());
        return new Response(null, { status: 204 });
      }
      if (secret && request.method === "DELETE") {
        backend.secrets.delete(secret);
        return new Response(null, { status: 204 });
      }
      if (route === "GET /jobs") return json([]);
      if (route === "GET /jobs/events") {
        let controller!: ReadableStreamDefaultController<Uint8Array>;
        const stream = new ReadableStream<Uint8Array>({
          start(c) {
            controller = c;
            streams.add(c);
          },
          cancel() {
            streams.delete(controller);
          },
        });
        request.signal.addEventListener("abort", () => {
          streams.delete(controller);
          controller.error(new DOMException("aborted", "AbortError"));
        });
        return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
      }
      return json({ error: { code: "http.not_found", params: {} } }, 404);
    },
  };
  return backend;
}

export function platformWith(state: BackendState): Platform {
  return {
    kind: "browser",
    connectBackend(onChange) {
      onChange(state);
      return () => undefined;
    },
  };
}

export const readyPlatform = platformWith({
  status: "ready",
  connection: { baseUrl: "http://test", token: "test-token" },
});

export function job(overrides: Partial<JobView> = {}): JobView {
  return {
    id: "job-1",
    type: "diagnostics.sleep",
    status: "running",
    progress: 0.5,
    attempts: 1,
    max_attempts: 3,
    error: null,
    created_at: "2026-11-04T10:00:00.000000+00:00",
    updated_at: "2026-11-04T10:00:01.000000+00:00",
    ...overrides,
  };
}
