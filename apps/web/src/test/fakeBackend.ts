// An in-memory stand-in for the backend API, for component tests (no network).
import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";
import type { BackendState, Platform } from "@/lib/platform";

type AppSettings = components["schemas"]["AppSettings"];
type ImportOutcome = components["schemas"]["ImportOutcome"];
type ImportPreview = components["schemas"]["ImportPreview"];
type PresetView = components["schemas"]["PresetView"];
type JobView = components["schemas"]["JobView"];
type CollectionView = components["schemas"]["CollectionView"];
type ExternalSearchView = components["schemas"]["ExternalSearchView"];
type TagView = components["schemas"]["TagView"];
type LibraryPaperRow = components["schemas"]["LibraryPaperRow"];
type FulltextPaper = components["schemas"]["FulltextPaper"];
type PaperDetail = components["schemas"]["PaperDetail"];
type AttachmentView = components["schemas"]["AttachmentView"];
type FindResults = components["schemas"]["FindResults"];
type AnchorView = components["schemas"]["AnchorView"];
type AnnotationView = components["schemas"]["AnnotationView"];
type AnnotationCreate = components["schemas"]["AnnotationCreate"];
type NoteView = components["schemas"]["NoteView"];
type LinkSuggestion = components["schemas"]["LinkSuggestion"];
type Backlink = components["schemas"]["Backlink"];
type ReviewView = components["schemas"]["ReviewView"];
type ReviewOverview = components["schemas"]["ReviewOverview"];
type CriterionView = components["schemas"]["CriterionView"];
type SearchOverview = components["schemas"]["SearchOverview"];
type SearchResultRow = components["schemas"]["SearchResultRow"];
type SourceProgress = components["schemas"]["SourceProgress"];
type MatrixView = components["schemas"]["MatrixView"];
type MatrixRowView = components["schemas"]["RowView"];
type MatrixColumnView = components["schemas"]["ColumnView"];
type MatrixCellView = components["schemas"]["CellView"];

export interface FakeBackend {
  fetch: FetchLike;
  settings: AppSettings;
  secrets: Map<string, string>;
  requests: { method: string; path: string; body: unknown }[];
  /** Push a job update to every open /jobs/events stream. */
  emitJob: (job: JobView) => void;
  reviews: ReviewView[];
  /** What GET /reviews/{id}/overview answers; a review with no records when missing. */
  reviewOverviews: Record<string, ReviewOverview>;
  /** Each review's screening criteria, in order; shortcuts are recomputed on change. */
  criteria: Record<string, CriterionView[]>;
  /** What GET /reviews/{id}/prisma answers; an empty review when missing (Task 35). */
  prismaCounts: Record<string, PrismaCounts>;
  /** Each review's edited PRISMA box titles. */
  prismaLabels: Record<string, Record<string, string>>;
  searchOverview: SearchOverview | null;
  searchResults: SearchResultRow[];
  searchHistory: SearchOverview[];
  /** Saved searches of databases without an API (Task 27). */
  externalSearches: ExternalSearchView[];
  /** Push a source update to the search's open event stream. */
  emitSource: (searchId: string, update: Partial<SourceProgress> & { source: string }) => void;
  /** End the search's event stream, as the backend does when all sources have answered. */
  finishSearch: (searchId: string) => void;
  /** Database presets verified with a real export (Task 26). */
  presets: PresetView[];
  importPreview: ImportPreview;
  /** When set, the preview fails with this error instead. */
  importPreviewError: { code: string; params: Record<string, unknown> } | null;
  importOutcome: ImportOutcome;
  collections: CollectionView[];
  tags: TagView[];
  papers: LibraryPaperRow[];
  /** What GET /papers/search answers for each query (best first); none when missing. */
  searchHits: Record<string, string[]>;
  /** What POST /fulltext/search answers for each query; nothing found when missing. */
  fulltextHits: Record<string, FulltextPaper[]>;
  details: Record<string, PaperDetail>;
  /** GET /attachments/{id}: what is special about a file; null means it is gone. */
  attachments: Record<string, Partial<AttachmentView> | null>;
  /** What searching inside a document answers for each query; no match when missing. */
  findResults: Record<string, FindResults>;
  anchors: Record<string, AnchorView>;
  notes: NoteView[];
  /** What POST /notes/{id} (PATCH) answers next instead of saving. */
  noteFailures: { status: number; code: string }[];
  suggestions: LinkSuggestion[];
  backlinks: Record<string, Backlink[]>;
  /** By attachment. */
  annotations: Record<string, AnnotationView[]>;
  /** Literature matrices (Tasks 51–52); type changes convert nothing here. */
  matrices: MatrixView[];
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
    reviewOverviews: {},
    criteria: {},
    prismaCounts: {},
    prismaLabels: {},
    searchOverview: null,
    searchResults: [],
    searchHistory: [],
    externalSearches: [],
    presets: [],
    importPreview: importPreview(),
    importPreviewError: null,
    importOutcome: importOutcome(),
    pdfReplies: [],
    collections: [],
    tags: [],
    papers: [],
    searchHits: {},
    fulltextHits: {},
    attachments: {},
    findResults: {},
    anchors: {},
    annotations: {},
    matrices: [],
    notes: [],
    noteFailures: [],
    suggestions: [],
    backlinks: {},
    details: {},
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
      if (route === "GET /reviews") {
        const inTrash = new URL(request.url, "http://test").searchParams.get("deleted") === "true";
        return json(backend.reviews.filter((r) => Boolean(r.deleted_at) === inTrash));
      }
      const trashOf = /^\/reviews\/([^/]+)(\/restore)?$/.exec(path);
      if (trashOf && (request.method === "DELETE" || (trashOf[2] && request.method === "POST"))) {
        const found = backend.reviews.find((r) => r.id === trashOf[1]);
        if (!found) return json({ error: { code: "review.not_found", params: {} } }, 404);
        if (request.method === "DELETE") {
          found.deleted_at ??= "2026-11-18T10:00:00Z";
          return new Response(null, { status: 204 });
        }
        found.deleted_at = null;
        return json(found);
      }
      if (route === "POST /reviews") {
        const created = review({
          id: `review-${String(backend.reviews.length + 1)}`,
          method: "prisma2020",
          ...(body as Partial<ReviewView>),
        });
        backend.reviews.push(created);
        return json(created, 201);
      }
      const criteriaOf = /^\/reviews\/([^/]+)\/criteria(?:\/(.+))?$/.exec(path);
      if (criteriaOf) {
        const reviewId = criteriaOf[1] ?? "";
        const rest = criteriaOf[2];
        const list = (backend.criteria[reviewId] ??= []);
        const reply = (status = 200) => json(withShortcuts(list), status);
        if (rest === undefined && request.method === "GET") return reply();
        if (rest === undefined && request.method === "POST") {
          const input = body as {
            kind: CriterionView["kind"];
            code?: string | null;
          } & Partial<CriterionView>;
          const prefix = input.kind === "inclusion" ? "I" : "E";
          const code =
            input.code?.toUpperCase() ??
            `${prefix}${String(list.filter((c) => c.code.startsWith(prefix)).length + 1)}`;
          if (list.some((c) => c.code === code)) {
            return json(
              { error: { code: "screening.criterion_code_taken", params: { code } } },
              409,
            );
          }
          const created = criterion({
            id: `criterion-${String(Date.now())}-${String(list.length)}`,
            kind: input.kind,
            code,
            text: input.text ?? "",
            stage: input.stage ?? null,
            keywords: input.keywords ?? [],
          });
          list.push(created);
          return json(
            withShortcuts(list).find((c) => c.id === created.id),
            201,
          );
        }
        if (rest === "order" && request.method === "PUT") {
          const ids = (body as { criterion_ids: string[] }).criterion_ids;
          const archived = list.filter((c) => c.archived);
          const ordered = ids.map((id) => list.find((c) => c.id === id)).filter((c) => !!c);
          backend.criteria[reviewId] = [...ordered, ...archived];
          return json(withShortcuts(backend.criteria[reviewId]));
        }
        const index = list.findIndex((c) => c.id === rest);
        const found = list[index];
        if (!found) {
          return json({ error: { code: "screening.criterion_not_found", params: {} } }, 404);
        }
        if (request.method === "DELETE") {
          if (found.used) {
            return json(
              { error: { code: "screening.criterion_in_use", params: { criterion_id: found.id } } },
              409,
            );
          }
          list.splice(index, 1);
          return new Response(null, { status: 204 });
        }
        if (request.method === "PATCH") {
          const changed = { ...found, ...(body as Partial<CriterionView>) };
          list.splice(index, 1);
          if (changed.archived) list.push(changed);
          else list.splice(list.filter((c) => !c.archived).length, 0, changed);
          return json(withShortcuts(list).find((c) => c.id === found.id));
        }
      }
      const prismaOf = /^\/reviews\/([^/]+)\/prisma(\/labels)?$/.exec(path);
      if (prismaOf) {
        const reviewId = prismaOf[1] ?? "";
        if (!prismaOf[2] && request.method === "GET") {
          return json(backend.prismaCounts[reviewId] ?? prismaCounts({ review_id: reviewId }));
        }
        if (request.method === "PUT") {
          backend.prismaLabels[reviewId] = (body as { labels: Record<string, string> }).labels;
        }
        return json({ labels: backend.prismaLabels[reviewId] ?? {} });
      }
      // The review panel asks for the optional quality stage (Task 38): off unless a test
      // wraps this backend with fakeQuality.
      if (request.method === "GET" && /^\/reviews\/[^/]+\/quality\/summary$/.test(path)) {
        return json({ enabled: false, questions: 0, papers: 0, assessed: 0, in_progress: 0 });
      }
      // Two-reviewer screening (Task 41): only the owner unless a test wraps this backend.
      if (request.method === "GET" && /^\/reviews\/[^/]+\/decisions\/reviewers$/.test(path)) {
        return json(["owner"]);
      }
      const overviewOf = /^\/reviews\/([^/]+)\/overview$/.exec(path)?.[1];
      if (overviewOf && request.method === "GET") {
        return json(
          backend.reviewOverviews[overviewOf] ?? reviewOverview({ review_id: overviewOf }),
        );
      }
      if (route === "POST /searches") {
        const { sources } = body as { sources: string[] };
        return json({ search_id: "search-1", sources }, 202);
      }
      if (route === "GET /searches") return json(backend.searchHistory);
      if (route === "GET /searches/external") return json(backend.externalSearches);
      if (route === "POST /searches/external") {
        const { review_id, source, query, name } = body as {
          review_id: string;
          source: string;
          query: string;
          name?: string | null;
        };
        const saved = externalSearch({
          id: `external-${String(backend.externalSearches.length + 1)}`,
          review_id,
          source,
          query,
          name: name ?? query,
        });
        backend.externalSearches.push(saved);
        return json(saved, 201);
      }
      if (route === "GET /imports/presets") return json(backend.presets);
      if (route === "POST /imports/preview") {
        return backend.importPreviewError
          ? json({ error: backend.importPreviewError }, 422)
          : json(backend.importPreview);
      }
      if (route === "POST /imports") return json(backend.importOutcome, 201);
      if (route === "GET /collections") return json(backend.collections);
      if (route === "POST /collections") {
        const { name, parent_id } = body as { name: string; parent_id: string | null };
        const created: CollectionView = {
          id: `collection-${String(backend.collections.length + 1)}`,
          parent_id,
          name,
          sort_order: 0,
          is_system: false,
          paper_count: 0,
        };
        backend.collections.push(created);
        return json(created, 201);
      }
      const collectionOf = /^\/collections\/([^/]+)$/.exec(path)?.[1];
      if (collectionOf && request.method === "PATCH") {
        const found = backend.collections.find((c) => c.id === collectionOf);
        if (!found) return json({ error: { code: "collection.not_found", params: {} } }, 404);
        Object.assign(found, body);
        return json(found);
      }
      if (collectionOf && request.method === "DELETE") {
        backend.collections = backend.collections.filter((c) => c.id !== collectionOf);
        return new Response(null, { status: 204 });
      }
      if (/^\/(collections|tags)\/[^/]+\/papers(\/remove)?$/.test(path)) {
        const { paper_ids } = body as { paper_ids: string[] };
        return json({ changed: paper_ids.length, unchanged: 0 });
      }
      if (route === "GET /tags") return json(backend.tags);
      if (route === "POST /tags") {
        const { name, color } = body as { name: string; color: string | null };
        const created: TagView = {
          id: `tag-${String(backend.tags.length + 1)}`,
          name,
          color,
          paper_count: 0,
        };
        backend.tags.push(created);
        return json(created, 201);
      }
      if (route === "GET /papers") {
        const query = new URL(request.url, "http://test").searchParams;
        const collection = query.get("collection_id");
        const tag = query.get("tag_id");
        return json(
          backend.papers.filter(
            (p) =>
              (!collection || p.collection_ids.includes(collection)) &&
              (!tag || p.tag_ids.includes(tag)),
          ),
        );
      }
      if (route === "GET /papers/search") {
        const q = new URL(request.url, "http://test").searchParams.get("q") ?? "";
        return json({ paper_ids: backend.searchHits[q] ?? [], elapsed_ms: 1.2 });
      }
      const attachmentOf = /^\/attachments\/([^/]+)$/.exec(path)?.[1];
      if (attachmentOf) {
        const special = backend.attachments[attachmentOf];
        if (special === null) {
          return json({ error: { code: "attachment.not_found", params: {} } }, 404);
        }
        return json(attachmentView({ id: attachmentOf, ...special }));
      }
      if (/^\/attachments\/[^/]+\/find$/.test(path)) {
        const q = new URL(request.url, "http://test").searchParams.get("q") ?? "";
        return json(backend.findResults[q] ?? { text: "ready", pages: [], total: 0 });
      }
      const matrixReply = matrixRoute(backend, request.method, path, body);
      if (matrixReply) return matrixReply;
      if (route === "GET /notes") return json(backend.notes);
      if (route === "POST /notes") {
        const id = `note-${String(backend.notes.length + 1)}`;
        const created = noteView({ id, ...(body as Partial<NoteView>) });
        backend.notes.push(created);
        return json(created, 201);
      }
      if (route === "GET /notes/suggest") return json(backend.suggestions);
      if (route === "GET /notes/search") {
        const q = new URL(request.url, "http://test").searchParams.get("q") ?? "";
        return json(
          backend.notes
            .filter((n) => `${n.title} ${n.body}`.includes(q))
            .map((n) => ({
              note_id: n.id,
              title: n.title,
              passage: [{ text: n.body, hit: false }],
            })),
        );
      }
      const paperNotesOf = /^\/papers\/([^/]+)\/notes$/.exec(path)?.[1];
      if (paperNotesOf) return json(backend.backlinks[paperNotesOf] ?? []);
      const [, noteId, noteAction] = /^\/notes\/([^/]+)(?:\/(\w+))?$/.exec(path) ?? [];
      if (noteId) {
        if (noteAction === "backlinks") return json(backend.backlinks[noteId] ?? []);
        const found = backend.notes.find((n) => n.id === noteId);
        const missing = () => json({ error: { code: "note.not_found", params: {} } }, 404);
        if (noteAction === "restore") {
          const back = noteView({ id: noteId, title: "Restored" });
          backend.notes.push(back);
          return json(back);
        }
        if (!found) return missing();
        if (noteAction === "append") {
          found.body = `${found.body}\n\n${(body as { text: string }).text}`;
          found.version += 1;
          return json(found);
        }
        if (request.method === "DELETE") {
          backend.notes = backend.notes.filter((n) => n !== found);
          return new Response(null, { status: 204 });
        }
        if (request.method === "PATCH") {
          const failure = backend.noteFailures.shift();
          if (failure) {
            return json({ error: { code: failure.code, params: {} } }, failure.status);
          }
          const { base_version: base, ...changes } = body as Partial<NoteView> & {
            base_version?: number;
          };
          if (base !== undefined && base !== found.version) {
            return json({ error: { code: "note.conflict", params: {} } }, 409);
          }
          Object.assign(found, changes, { version: found.version + 1 });
        }
        return json(found);
      }
      const annotationsOf = /^\/attachments\/([^/]+)\/annotations$/.exec(path)?.[1];
      if (annotationsOf) {
        const list = (backend.annotations[annotationsOf] ??= []);
        if (request.method === "GET") return json(list);
        const { anchor, color, comment } = body as AnnotationCreate;
        const id = `annotation-${String(list.length + 1)}`;
        const created = annotationView({
          id,
          color,
          comment,
          kind: anchor.kind === "area" ? "area" : "highlight",
          anchor: anchorView({ id: `anchor-${id}`, attachment_id: annotationsOf, ...anchor }),
        });
        list.push(created);
        return json(created, 201);
      }
      const annotationOf = /^\/annotations\/([^/]+)$/.exec(path)?.[1];
      if (annotationOf) {
        for (const [key, list] of Object.entries(backend.annotations)) {
          const found = list.find((a) => a.id === annotationOf);
          if (!found) continue;
          if (request.method === "DELETE") {
            backend.annotations[key] = list.filter((a) => a !== found);
            return new Response(null, { status: 204 });
          }
          Object.assign(found, body);
          return json(found);
        }
        return json({ error: { code: "annotation.not_found", params: {} } }, 404);
      }
      const anchorOf = /^\/anchors\/([^/]+)$/.exec(path)?.[1];
      if (anchorOf) {
        const anchor = backend.anchors[anchorOf];
        return anchor
          ? json(anchor)
          : json({ error: { code: "anchor.not_found", params: {} } }, 404);
      }
      if (/^\/attachments\/[^/]+\/file$/.test(path) && request.method === "PUT") {
        return json(attachmentView({ text_status: "pending" }));
      }
      if (route === "POST /fulltext/search") {
        const { q, paper_ids, limit } = body as {
          q: string;
          paper_ids: string[];
          limit: number;
        };
        const all = (backend.fulltextHits[q] ?? []).filter((p) => paper_ids.includes(p.paper_id));
        return json({
          papers: all.slice(0, limit),
          total_papers: all.length,
          total_pages: all.reduce((sum, p) => sum + p.page_hits, 0),
          truncated: false,
          elapsed_ms: 1.2,
        });
      }
      const paperOf = /^\/papers\/([^/]+)$/.exec(path)?.[1];
      if (paperOf && paperOf !== "reading-status") {
        const detail = backend.details[paperOf];
        if (!detail) return json({ error: { code: "paper.not_found", params: {} } }, 404);
        if (request.method === "PATCH") {
          const { citekey } = body as { citekey: string };
          if (citekey === "taken") {
            return json({ error: { code: "citekey.taken", params: { citekey } } }, 409);
          }
          detail.citekey = citekey;
        }
        return json(detail);
      }
      if (route === "PATCH /papers/reading-status") {
        const { paper_ids } = body as { paper_ids: string[] };
        return json({ changed: paper_ids.length, unchanged: 0 });
      }
      if (route === "POST /pdfs/from-paths") {
        // A path with "dup" in it is already in the library; "bad" is not a PDF.
        const { paths } = body as { paths: string[] };
        return json(
          paths.map((path, index) =>
            path.includes("bad")
              ? { path, error: { code: "pdf.not_a_pdf", params: { file_name: path } } }
              : {
                  path,
                  added: {
                    status: path.includes("dup") ? "duplicate" : "added",
                    paper_id: `paper-${String(index)}`,
                    attachment_id: `att-${String(index)}`,
                    job_id: null,
                    file_name: path.split("/").pop(),
                  },
                },
          ),
        );
      }
      if (route === "POST /pdfs/open-access") {
        const { paper_ids } = body as { paper_ids: string[] };
        return json(
          {
            job_ids: paper_ids.slice(1).map((id) => `job-${id}`),
            already_have_pdf: 0,
            no_source: 1,
          },
          202,
        );
      }
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
    research_questions: [],
    protocol: null,
    created_at: "2026-11-04T10:00:00+00:00",
    ...overrides,
  };
}

export function criterion(overrides: Partial<CriterionView> = {}): CriterionView {
  return {
    id: "criterion-1",
    kind: "exclusion",
    code: "E1",
    text: "Not about code review",
    stage: null,
    position: 0,
    archived: false,
    used: false,
    shortcuts: { title_abstract: null, full_text: null },
    keywords: [],
    ...overrides,
  };
}

/** The backend's rule: per stage, the first nine active criteria in order get keys 1-9. */
export function withShortcuts(list: CriterionView[]): CriterionView[] {
  const keys = { title_abstract: 0, full_text: 0 };
  return list.map((c, position) => {
    const shortcuts: CriterionView["shortcuts"] = { title_abstract: null, full_text: null };
    for (const stage of ["title_abstract", "full_text"] as const) {
      if (!c.archived && (c.stage === null || c.stage === stage) && keys[stage] < 9) {
        keys[stage] += 1;
        shortcuts[stage] = keys[stage];
      }
    }
    return { ...c, position, shortcuts };
  });
}

type PrismaCounts = components["schemas"]["PrismaCounts"];
type PrismaBranch = Omit<PrismaCounts["databases"], "sources">;

export function prismaBranch(overrides: Partial<PrismaBranch> = {}): PrismaBranch {
  return {
    identified: 0,
    unlogged: 0,
    duplicates: 0,
    not_taken: 0,
    screened: 0,
    excluded: 0,
    awaiting_screening: 0,
    sought: 0,
    not_retrieved: 0,
    assessed: 0,
    awaiting_full_text: 0,
    excluded_reports: [],
    included: 0,
    ...overrides,
  };
}

export function prismaCounts(overrides: Partial<PrismaCounts> = {}): PrismaCounts {
  return {
    review_id: "review-1",
    databases: { ...prismaBranch(), sources: [] },
    other_methods: { ...prismaBranch(), methods: [] },
    included: 0,
    ...overrides,
  };
}

export function reviewOverview(overrides: Partial<ReviewOverview> = {}): ReviewOverview {
  const empty = { eligible: 0, decided: 0, pending: 0, included: 0, excluded: 0, maybe: 0 };
  return {
    review_id: "review-1",
    records: 0,
    stages: [
      { stage: "title_abstract", ...empty },
      { stage: "full_text", ...empty },
    ],
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
    thesis_type: null,
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
    onOpenRequests: () => () => undefined,
    openExternal: () => Promise.resolve(),
    copyText: () => Promise.resolve(),
    saveFile: () => Promise.resolve(),
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

export function externalSearch(overrides: Partial<ExternalSearchView> = {}): ExternalSearchView {
  return {
    id: "external-1",
    review_id: "review-1",
    name: "Scopus main query",
    source: "Scopus",
    query: 'TITLE-ABS-KEY("code review")',
    created_at: "2026-10-01T09:00:00Z",
    imports: 0,
    last_searched_at: null,
    last_retrieved: null,
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

export function libraryPaper(overrides: Partial<LibraryPaperRow> = {}): LibraryPaperRow {
  return {
    id: "paper-1",
    title: "Automated code review with LLMs",
    first_author: "Ayşe Yılmaz",
    author_count: 2,
    year: 2024,
    venue: "ICSE",
    venue_type: "conference",
    thesis_type: null,
    doi: "10.1145/1",
    citekey: null,
    citation_count: 4,
    reading_status: "unread",
    tag_ids: [],
    collection_ids: [],
    pdf: "none",
    added_at: "2026-11-11T10:00:00+00:00",
    ...overrides,
  };
}

export function anchorView(overrides: Partial<AnchorView> = {}): AnchorView {
  return {
    id: "anchor-1",
    attachment_id: "att-1",
    kind: "text",
    status: "verified",
    page: 1,
    rects: [[100, 600, 300, 620]],
    quote: "forty-two participants",
    prefix: "We interviewed",
    suffix: "in twelve schools.",
    paper: {
      id: "paper-1",
      title: "First paper",
      first_author: "Ada Lovelace",
      author_count: 2,
      year: 2024,
      citekey: "lovelace2024first",
    },
    ...overrides,
  };
}

export function annotationView(overrides: Partial<AnnotationView> = {}): AnnotationView {
  return {
    id: "annotation-1",
    kind: "highlight",
    color: "yellow",
    comment: "",
    anchor: anchorView(),
    created_at: "2026-11-25T10:00:00Z",
    updated_at: "2026-11-25T10:00:00Z",
    ...overrides,
  };
}

export function noteView(overrides: Partial<NoteView> = {}): NoteView {
  return {
    id: "note-1",
    title: "First note",
    body: "",
    parent_id: null,
    paper_id: null,
    review_id: null,
    version: 1,
    links: [],
    created_at: "2026-11-25T10:00:00Z",
    updated_at: "2026-11-25T10:00:00Z",
    ...overrides,
  };
}

export function attachmentView(overrides: Partial<AttachmentView> = {}): AttachmentView {
  return {
    id: "att-1",
    paper_id: "paper-1",
    kind: "pdf",
    file_name: `${overrides.id ?? "att-1"}.pdf`,
    sha256: "0".repeat(64),
    size: 1000,
    page_count: 40,
    text_status: "ok",
    error: null,
    source: "manual",
    created_at: "2026-11-25T10:00:00Z",
    ...overrides,
  };
}

export function paperDetail(overrides: Partial<PaperDetail> = {}): PaperDetail {
  return {
    id: "paper-1",
    title: "Automated code review with LLMs",
    abstract: "We study how LLMs review code.",
    year: 2024,
    venue: "ICSE",
    venue_type: "conference",
    thesis_type: null,
    volume: null,
    issue: null,
    pages: "1-12",
    language: "en",
    url: null,
    oa_url: null,
    citation_count: 4,
    reading_status: "unread",
    citekey: "yilmaz2024automated",
    retraction_status: "none",
    added_at: "2026-11-11T10:00:00+00:00",
    authors: [
      {
        display_name: "Ayşe Yılmaz",
        family: "Yılmaz",
        given: "Ayşe",
        orcid: null,
        affiliation: null,
      },
    ],
    identifiers: { doi: "10.1145/1" },
    tag_ids: [],
    collection_ids: [],
    attachments: [],
    related: [],
    ...overrides,
  };
}

const notFound = (code: string) => json({ error: { code, params: {} } }, 404);

/** The matrix endpoints, on `backend.matrices`. */
function matrixRoute(
  backend: FakeBackend,
  method: string,
  path: string,
  body: unknown,
): Response | null {
  const listOf = /^\/reviews\/([^/]+)\/matrices$/.exec(path)?.[1];
  if (listOf && method === "GET") {
    return json(
      backend.matrices
        .filter((m) => m.review_id === listOf)
        .map((m) => ({
          id: m.id,
          review_id: m.review_id,
          name: m.name,
          columns: m.columns.length,
          created_at: "2026-11-26T10:00:00Z",
        })),
    );
  }
  if (listOf && method === "POST") {
    const made = matrixView({
      id: `matrix-${String(backend.matrices.length + 1)}`,
      review_id: listOf,
      name: (body as { name: string }).name,
    });
    backend.matrices.push(made);
    return json(made, 201);
  }
  const [, matrixId, rest = ""] = /^\/matrices\/([^/]+)(.*)$/.exec(path) ?? [];
  if (!matrixId) return null;
  const matrix = backend.matrices.find((m) => m.id === matrixId);
  if (!matrix) return notFound("matrix.not_found");
  if (rest === "" && method === "GET") return json(matrix);
  if (rest === "/columns" && method === "POST") {
    const given = body as { name: string; data_type: MatrixColumnView["data_type"] } & {
      instruction?: string | null;
      options?: { label: string }[];
    };
    const column = matrixColumn({
      id: `column-${String(matrix.columns.length + 1)}`,
      name: given.name,
      instruction: given.instruction ?? null,
      data_type: given.data_type,
      options: (given.options ?? []).map((o, i) => ({
        id: `option-${String(i + 1)}`,
        label: o.label,
      })),
      sort_order: matrix.columns.length,
    });
    matrix.columns.push(column);
    return json(column, 201);
  }
  const cellOf = /^\/cells\/([^/]+)\/([^/]+)$/.exec(rest);
  if (cellOf && method === "PUT") {
    const [, paperId, columnId] = cellOf;
    const row = matrix.rows.find((r) => r.paper_id === paperId);
    if (!row) return notFound("matrix.paper_not_included");
    const { value, kept_text: kept = null } = body as {
      value: MatrixCellView["value"];
      kept_text?: string | null;
    };
    row.cells = row.cells.filter((c) => c.column_id !== columnId);
    if (value === null && kept === null) return json(null);
    const cell = {
      column_id: columnId ?? "",
      value,
      kept_text: kept,
      origin: "manual" as const,
      updated_at: "2026-11-26T10:00:00Z",
      evidence: [],
    };
    row.cells.push(cell);
    return json(cell);
  }
  const [, columnId, action] = /^\/columns\/([^/]+)(?:\/(\w+))?$/.exec(rest) ?? [];
  const column = matrix.columns.find((c) => c.id === columnId);
  if (columnId && !column) return notFound("matrix.column_not_found");
  if (column && method === "PATCH") {
    const patch = body as { name?: string; instruction?: string };
    if (patch.name !== undefined) column.name = patch.name;
    if (patch.instruction !== undefined) column.instruction = patch.instruction || null;
    return json(column);
  }
  if (column && method === "DELETE") {
    matrix.columns = matrix.columns.filter((c) => c !== column);
    for (const row of matrix.rows) row.cells = row.cells.filter((c) => c.column_id !== column.id);
    return new Response(null, { status: 204 });
  }
  if (column && action === "type") {
    const change = body as { data_type: MatrixColumnView["data_type"]; dry_run: boolean };
    const cells = matrix.rows.flatMap((r) => r.cells.filter((c) => c.column_id === column.id));
    if (!change.dry_run) column.data_type = change.data_type;
    return json({
      column,
      applied: !change.dry_run,
      cells: cells.length,
      converted: cells.length,
      kept: [],
    });
  }
  return null;
}

export function matrixView(overrides: Partial<MatrixView> = {}): MatrixView {
  return {
    id: "matrix-1",
    review_id: "review-1",
    name: "Matrix",
    columns: [],
    rows: [],
    coverage: { filled: 0, sourced: 0, rows: 0, rows_sourced: 0 },
    ...overrides,
  };
}

export function matrixColumn(overrides: Partial<MatrixColumnView> = {}): MatrixColumnView {
  return {
    id: "column-1",
    name: "Method",
    instruction: null,
    data_type: "text",
    options: [],
    sort_order: 0,
    ...overrides,
  };
}

export function matrixRow(overrides: Partial<MatrixRowView> = {}): MatrixRowView {
  return {
    paper_id: "paper-1",
    title: "A paper",
    year: 2024,
    venue: null,
    first_author: "Kim",
    author_count: 1,
    reading_status: "unread",
    included: true,
    cells: [],
    ...overrides,
  };
}
