// An in-memory stand-in for the backend API, for component tests (no network).
import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";
import type { BackendState, Platform } from "@/lib/platform";

type AppSettings = components["schemas"]["AppSettings"];
type ImportOutcome = components["schemas"]["ImportOutcome"];
type ImportPreview = components["schemas"]["ImportPreview"];
type JobView = components["schemas"]["JobView"];
type ReviewView = components["schemas"]["ReviewView"];
type SearchOverview = components["schemas"]["SearchOverview"];
type SearchResultRow = components["schemas"]["SearchResultRow"];
type SourceProgress = components["schemas"]["SourceProgress"];

export interface FakeBackend {
  fetch: FetchLike;
  settings: AppSettings;
  secrets: Map<string, string>;
  requests: { method: string; path: string; body: unknown }[];
  /** Push a job update to every open /jobs/events stream. */
  emitJob: (job: JobView) => void;
  reviews: ReviewView[];
  searchOverview: SearchOverview | null;
  searchResults: SearchResultRow[];
  searchHistory: SearchOverview[];
  /** Push a source update to the search's open event stream. */
  emitSource: (searchId: string, update: Partial<SourceProgress> & { source: string }) => void;
  /** End the search's event stream, as the backend does when all sources have answered. */
  finishSearch: (searchId: string) => void;
  importPreview: ImportPreview;
  /** When set, the preview fails with this error instead. */
  importPreviewError: { code: string; params: Record<string, unknown> } | null;
  importOutcome: ImportOutcome;
  /** What the next POST /pdfs answers, in order; "added" when empty. */
  pdfReplies: (
    | { status: "added" | "duplicate" }
    | { error: { code: string; params: Record<string, unknown> }; httpStatus: number }
  )[];
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function fakeBackend(initial: Partial<AppSettings> = {}): FakeBackend {
  const streams = new Set<ReadableStreamDefaultController<Uint8Array>>();
  const encoder = new TextEncoder();
  let eventId = 0;
  const searchStreams = new Map<string, ReadableStreamDefaultController<Uint8Array>>();

  const backend: FakeBackend = {
    settings: { language: null, theme: "system", sources_email: null, ...initial },
    secrets: new Map(),
    requests: [],
    reviews: [],
    searchOverview: null,
    searchResults: [],
    searchHistory: [],
    importPreview: importPreview(),
    importPreviewError: null,
    importOutcome: importOutcome(),
    pdfReplies: [],
    emitSource(searchId, update) {
      const data = {
        state: "searching",
        retrieved: null,
        total_reported: null,
        wait_seconds: null,
        error_code: null,
        ...update,
      };
      searchStreams
        .get(searchId)
        ?.enqueue(encoder.encode(`event: source\ndata: ${JSON.stringify(data)}\n\n`));
    },
    finishSearch(searchId) {
      const stream = searchStreams.get(searchId);
      stream?.enqueue(encoder.encode(`event: finished\ndata: {}\n\n`));
      stream?.close();
      searchStreams.delete(searchId);
    },
    emitJob(job) {
      eventId += 1;
      const chunk = encoder.encode(
        `event: job\nid: ${String(eventId)}\ndata: ${JSON.stringify(job)}\n\n`,
      );
      for (const stream of streams) stream.enqueue(chunk);
    },
    async fetch(request) {
      const path = new URL(request.url, "http://test").pathname;
      const isJson = request.headers.get("Content-Type")?.includes("json") ?? false;
      const body: unknown =
        request.method === "GET" || request.method === "DELETE"
          ? undefined
          : isJson
            ? await request.json()
            : await request.arrayBuffer();
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
      if (route === "GET /reviews") return json(backend.reviews);
      if (route === "POST /reviews") {
        const created = review({
          id: `review-${String(backend.reviews.length + 1)}`,
          ...(body as Partial<ReviewView>),
        });
        backend.reviews.push(created);
        return json(created, 201);
      }
      if (route === "POST /searches") {
        const { sources } = body as { sources: string[] };
        return json({ search_id: "search-1", sources }, 202);
      }
      if (route === "GET /searches") return json(backend.searchHistory);
      if (route === "POST /imports/preview") {
        return backend.importPreviewError
          ? json({ error: backend.importPreviewError }, 422)
          : json(backend.importPreview);
      }
      if (route === "POST /imports") return json(backend.importOutcome, 201);
      if (route === "POST /pdfs") {
        const fileName = new URL(request.url, "http://test").searchParams.get("file_name") ?? "";
        const reply = backend.pdfReplies.shift() ?? { status: "added" };
        if ("error" in reply) return json({ error: reply.error }, reply.httpStatus);
        return json(
          {
            status: reply.status,
            paper_id: "paper-pdf",
            attachment_id: "attachment-1",
            job_id: reply.status === "added" ? "job-pdf" : null,
            file_name: fileName,
          },
          201,
        );
      }
      if (/^\/reviews\/[^/]+\/records$/.test(path) || route === "POST /library/papers") {
        const { paper_ids } = body as { paper_ids: string[] };
        return json({ added: paper_ids.length, already_present: 0 });
      }
      const eventsOf = /^\/searches\/([^/]+)\/events$/.exec(path)?.[1];
      if (eventsOf) {
        if (eventsOf !== "search-1") {
          return json({ error: { code: "search.not_found", params: {} } }, 404);
        }
        const stream = new ReadableStream<Uint8Array>({
          start(c) {
            searchStreams.set(eventsOf, c);
          },
        });
        return new Response(stream, { headers: { "Content-Type": "text/event-stream" } });
      }
      if (/^\/searches\/[^/]+\/results$/.test(path)) return json(backend.searchResults);
      if (/^\/searches\/[^/]+$/.test(path)) {
        return backend.searchOverview
          ? json(backend.searchOverview)
          : json({ error: { code: "search.not_found", params: {} } }, 404);
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

export function review(overrides: Partial<ReviewView> = {}): ReviewView {
  return {
    id: "review-1",
    title: "LLM Code Review SLR",
    method: "kitchenham_slr",
    status: "active",
    created_at: "2026-11-04T10:00:00+00:00",
    ...overrides,
  };
}

export function overview(overrides: Partial<SearchOverview> = {}): SearchOverview {
  return {
    search_id: "search-1",
    review_id: "review-1",
    query: "code review",
    filters: null,
    initiated_via: "gui",
    started_at: "2026-11-04T10:00:00+00:00",
    runs: [
      {
        source: "arxiv",
        status: "ok",
        translated_query: 'all:"code review" AND all:LLM',
        executed_at: "2026-11-04T10:00:00+00:00",
        total_reported: 1,
        retrieved_count: 1,
        error: null,
      },
      {
        source: "crossref",
        status: "ok",
        translated_query: "code review LLM",
        executed_at: "2026-11-04T10:00:00+00:00",
        total_reported: 1,
        retrieved_count: 1,
        error: null,
      },
    ],
    retrieved: 1,
    unique: 1,
    duplicates: 0,
    in_library: 0,
    ...overrides,
  };
}

export function resultRow(overrides: Partial<SearchResultRow> = {}): SearchResultRow {
  return {
    paper_id: "p1",
    title: "A paper",
    first_author: "Ayşe Yılmaz",
    author_count: 2,
    year: 2024,
    venue: "ICSE",
    venue_type: "conference",
    abstract: null,
    citation_count: 3,
    doi: null,
    arxiv_id: null,
    url: null,
    oa_url: null,
    language: "en",
    is_retracted: false,
    in_library: false,
    in_review: false,
    sources: [{ source: "openalex", rank: 1, match_method: "new", match_score: null }],
    ...overrides,
  };
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

export function importPreview(overrides: Partial<ImportPreview> = {}): ImportPreview {
  return {
    format: "ris",
    total: 3,
    readable: 2,
    issues: [{ code: "import.entry_no_title", line: 9, key: null, detail: null }],
    new: 1,
    known: 0,
    in_library: 1,
    repeated: 0,
    warnings: { no_authors: 1 },
    sample: [
      {
        line: 1,
        key: "scopus-1",
        title: "Automated code review with LLMs",
        first_author: "A. Yılmaz",
        author_count: 2,
        year: 2024,
        venue: "TSE",
        venue_type: "journal",
        doi: "10.1109/tse.2024.1",
        warnings: [],
        status: "in_library",
        match_method: "doi",
      },
      {
        line: 15,
        key: null,
        title: "A chapter",
        first_author: null,
        author_count: 0,
        year: 2020,
        venue: null,
        venue_type: "chapter",
        doi: null,
        warnings: ["no_authors"],
        status: "new",
        match_method: "new",
      },
    ],
    ...overrides,
  };
}

export function importOutcome(overrides: Partial<ImportOutcome> = {}): ImportOutcome {
  return {
    format: "ris",
    total: 3,
    imported: 2,
    issues: [],
    new_papers: 1,
    search_id: "search-import",
    added_to_review: 2,
    added_to_library: 0,
    ...overrides,
  };
}
