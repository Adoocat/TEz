// A screening backend for component tests: the queue, records and append-only decisions of
// one review, following the real service's rules closely enough for the screen (Task 32).
import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";

import { withShortcuts, type FakeBackend } from "./fakeBackend";

type Stage = components["schemas"]["ScreeningStage"];
type DecisionView = components["schemas"]["DecisionView"];
type RecordState = components["schemas"]["RecordState"];

export interface ScreeningPaper {
  paper_id: string;
  title: string;
  abstract?: string | null;
  authors?: string[];
  attachments?: components["schemas"]["AttachmentView"][];
}

export interface FakeScreening {
  fetch: FetchLike;
  decisions: DecisionView[];
  /** Fail the next decision with this error code. */
  failNext: string | null;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export function fakeScreening(
  backend: FakeBackend,
  reviewId: string,
  papers: ScreeningPaper[],
): FakeScreening {
  const screening: FakeScreening = { fetch, decisions: [], failNext: null };
  let made = 0;

  function head(paperId: string, stage: Stage): DecisionView | undefined {
    const chain = screening.decisions.filter((d) => d.paper_id === paperId && d.stage === stage);
    return chain.at(-1);
  }
  function state(paperId: string, stage: Stage): RecordState {
    const decision = head(paperId, stage)?.decision;
    return !decision || decision === "undecided" ? "undecided" : decision;
  }
  function queue(stage: Stage) {
    return stage === "title_abstract"
      ? papers
      : papers.filter((p) => ["include", "maybe"].includes(state(p.paper_id, "title_abstract")));
  }
  function item(paper: ScreeningPaper, stage: Stage, position: number) {
    const decision = head(paper.paper_id, stage);
    return {
      paper_id: paper.paper_id,
      position,
      state: state(paper.paper_id, stage),
      decision_id: decision?.id ?? null,
      criterion_id: decision?.criterion_id ?? null,
      title: paper.title,
      year: 2024,
      venue: null,
      first_author: paper.authors?.[0] ?? null,
      author_count: paper.authors?.length ?? 0,
    };
  }
  function write(paperId: string, stage: Stage, fields: Partial<DecisionView>): DecisionView {
    made += 1;
    const decision: DecisionView = {
      id: `decision-${String(made)}`,
      paper_id: paperId,
      stage,
      decision: "include",
      criterion_id: null,
      note: null,
      reviewer: "owner",
      supersedes_id: head(paperId, stage)?.id ?? null,
      created_at: new Date(Date.UTC(2026, 10, 16, 0, 0, made)).toISOString(),
      ...fields,
    };
    screening.decisions.push(decision);
    return decision;
  }

  async function fetch(request: Request): Promise<Response> {
    const url = new URL(request.url, "http://test");
    const match = new RegExp(
      `^/reviews/${reviewId}/screening/(title_abstract|full_text)(/.*)?$`,
    ).exec(url.pathname);
    if (!match) return backend.fetch(request);
    const stage = match[1] as Stage;
    const rest = match[2] ?? "";
    const body: unknown = request.method === "POST" ? await request.json() : undefined;
    backend.requests.push({ method: request.method, path: url.pathname, body });
    const papersHere = queue(stage);

    if (rest === "" && request.method === "GET") {
      const items = papersHere.map((paper, index) => item(paper, stage, index + 1));
      const count = (s: RecordState) => items.filter((i) => i.state === s).length;
      return json({
        stage,
        counts: {
          total: items.length,
          undecided: count("undecided"),
          include: count("include"),
          exclude: count("exclude"),
          maybe: count("maybe"),
          not_retrieved: count("not_retrieved"),
        },
        items,
      });
    }
    if (rest === "/criteria") {
      return json(
        withShortcuts(backend.criteria[reviewId] ?? [])
          .filter((c) => !c.archived && (c.stage === null || c.stage === stage))
          .map((c) => ({
            id: c.id,
            kind: c.kind,
            code: c.code,
            text: c.text,
            shortcut: c.shortcuts[stage],
            keywords: c.keywords,
          })),
      );
    }
    const recordId = /^\/records\/(.+)$/.exec(rest)?.[1];
    if (recordId) {
      const index = papersHere.findIndex((p) => p.paper_id === recordId);
      const paper = papersHere[index];
      if (!paper) return json({ error: { code: "screening.record_not_found", params: {} } }, 404);
      const decision = head(paper.paper_id, stage) ?? null;
      return json({
        ...item(paper, stage, index + 1),
        total: papersHere.length,
        decision,
        abstract: paper.abstract ?? null,
        authors: paper.authors ?? [],
        doi: null,
        retraction_status: "none",
        attachments: paper.attachments ?? [],
      });
    }
    if (rest === "/decisions") {
      if (screening.failNext) {
        const code = screening.failNext;
        screening.failNext = null;
        return json({ error: { code, params: {} } }, 400);
      }
      const input = body as {
        paper_id: string;
        decision: DecisionView["decision"];
        criterion_id: string | null;
        note: string | null;
      };
      return json(
        write(input.paper_id, stage, {
          decision: input.decision,
          criterion_id: input.criterion_id,
          note: input.note,
        }),
        201,
      );
    }
    if (rest === "/undo") {
      const target = screening.decisions.find(
        (d) => d.id === (body as { decision_id: string }).decision_id,
      );
      if (!target)
        return json({ error: { code: "screening.decision_not_found", params: {} } }, 404);
      const before = screening.decisions.find((d) => d.id === target.supersedes_id);
      return json(
        write(target.paper_id, stage, {
          decision: before?.decision ?? "undecided",
          criterion_id: before?.criterion_id ?? null,
          note: before?.note ?? null,
        }),
        201,
      );
    }
    return json({ error: { code: "http.not_found", params: {} } }, 404);
  }

  return screening;
}
