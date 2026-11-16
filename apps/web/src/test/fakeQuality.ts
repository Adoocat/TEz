// A quality-assessment backend for component tests (Task 38): one review's switch, question
// set and answers, following the real service's rules closely enough for the screens.
import type { components } from "@/api/schema";
import type { FetchLike } from "@/app/backend";

import type { FakeBackend } from "./fakeBackend";

type QuestionView = components["schemas"]["QuestionView"];
type ScaleOption = components["schemas"]["ScaleOption"];
type QualityCatalog = components["schemas"]["QualityCatalog"];
type AnswerView = components["schemas"]["AnswerView"];

export interface QualityPaper {
  paper_id: string;
  title: string;
  year?: number | null;
  first_author?: string | null;
}

export interface FakeQuality {
  fetch: FetchLike;
  enabled: boolean;
  questions: QuestionView[];
  /** answers[paperId][questionId] */
  answers: Record<string, Record<string, AnswerView>>;
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const fail = (code: string, status: number) => json({ error: { code, params: {} } }, status);

const yesNo = [
  { value: "yes", labels: { en: "Yes", tr: "Evet" }, score: 1 },
  { value: "no", labels: { en: "No", tr: "Hayır" }, score: 0 },
  { value: "not_applicable", labels: { en: "Not applicable", tr: "Uygulanamaz" }, score: null },
];

export const qualityCatalog: QualityCatalog = {
  scales: [
    {
      key: "yes_partly_no",
      options: [
        { value: "yes", labels: { en: "Yes", tr: "Evet" }, score: 1 },
        { value: "partly", labels: { en: "Partly", tr: "Kısmen" }, score: 0.5 },
        { value: "no", labels: { en: "No", tr: "Hayır" }, score: 0 },
      ],
    },
    { key: "nhlbi", options: yesNo },
    {
      key: "good_fair_poor",
      options: [
        { value: "good", labels: { en: "Good", tr: "İyi" }, score: null },
        { value: "fair", labels: { en: "Fair", tr: "Orta" }, score: null },
        { value: "poor", labels: { en: "Poor", tr: "Zayıf" }, score: null },
      ],
    },
  ],
  templates: [
    {
      key: "nhlbi_case_series",
      title: "Quality Assessment Tool for Case Series Studies",
      publisher: "National Heart, Lung, and Blood Institute (NHLBI)",
      design: "case_series",
      version: "2021-07",
      license: "Public domain (U.S. Government work, 17 U.S.C. § 105)",
      source_url: "https://www.nhlbi.nih.gov/health-topics/study-quality-assessment-tools",
      questions: ["Were the cases consecutive?", "Was the intervention clearly described?"],
      scale: "nhlbi",
      rating_question: "Quality rating (Good, Fair, or Poor)",
      rating_scale: "good_fair_poor",
    },
  ],
};

export function fakeQuality(
  backend: FakeBackend,
  reviewId: string,
  papers: QualityPaper[],
): FakeQuality {
  const quality: FakeQuality = { fetch, enabled: false, questions: [], answers: {} };
  let made = 0;

  function add(text: string, scale: ScaleOption[], template: string | null): QuestionView {
    made += 1;
    const question: QuestionView = {
      id: `question-${String(made)}`,
      text,
      guidance: null,
      scale,
      sort_order: quality.questions.length,
      template,
    };
    quality.questions.push(question);
    return question;
  }
  function localized(key: string, language: "en" | "tr"): ScaleOption[] {
    const preset = qualityCatalog.scales.find((s) => s.key === key);
    return (preset?.options ?? []).map((o) => ({
      value: o.value,
      label: o.labels[language] ?? o.value,
      score: o.score,
    }));
  }
  function row(paper: QualityPaper) {
    const answers = quality.answers[paper.paper_id] ?? {};
    let score = 0;
    let max = 0;
    let scored = false;
    for (const question of quality.questions) {
      const numeric = question.scale.flatMap((o) => (o.score == null ? [] : [o.score]));
      if (numeric.length === 0) continue;
      const chosen = question.scale.find((o) => o.value === answers[question.id]?.answer);
      if (chosen && chosen.score == null) continue;
      scored = true;
      max += Math.max(...numeric);
      score += chosen?.score ?? 0;
    }
    return {
      paper_id: paper.paper_id,
      title: paper.title,
      year: paper.year ?? null,
      first_author: paper.first_author ?? null,
      answered: quality.questions.filter((q) => answers[q.id]?.answer != null).length,
      questions: quality.questions.length,
      score: scored ? score : null,
      max_score: scored ? max : null,
    };
  }
  function assessment(paperId: string) {
    return { paper_id: paperId, answers: Object.values(quality.answers[paperId] ?? {}) };
  }

  async function fetch(request: Request): Promise<Response> {
    const url = new URL(request.url, "http://test");
    const base = `/reviews/${reviewId}/quality`;
    if (url.pathname !== "/quality/catalog" && !url.pathname.startsWith(base)) {
      return backend.fetch(request);
    }
    const body: unknown = ["GET", "DELETE"].includes(request.method)
      ? undefined
      : await request.json();
    backend.requests.push({ method: request.method, path: url.pathname, body });
    const rest = url.pathname.slice(base.length);
    const route = `${request.method} ${rest}`;

    if (url.pathname === "/quality/catalog") return json(qualityCatalog);
    if (route === "GET ") return json({ enabled: quality.enabled, questions: quality.questions });
    if (route === "PUT /setting") {
      quality.enabled = (body as { enabled: boolean }).enabled;
      return json({ enabled: quality.enabled, questions: quality.questions });
    }
    if (route === "GET /summary") {
      const rows = papers.map(row);
      const total = quality.questions.length;
      return json({
        enabled: quality.enabled,
        questions: total,
        papers: rows.length,
        assessed: rows.filter((r) => total > 0 && r.answered === total).length,
        in_progress: rows.filter((r) => r.answered > 0 && r.answered < total).length,
      });
    }
    if (route === "POST /questions") {
      const { questions } = body as {
        questions: { text: string; scale: { options: ScaleOption[] } }[];
      };
      return json(
        questions.map((q) => add(q.text, q.scale.options, null)),
        201,
      );
    }
    const template = /^POST \/templates\/(.+)$/.exec(route)?.[1];
    if (template) {
      const found = qualityCatalog.templates.find((t) => t.key === template);
      if (!found) return fail("quality.template_unknown", 404);
      const { language } = body as { language: "en" | "tr" };
      const created = found.questions.map((text) =>
        add(text, localized(found.scale, language), found.key),
      );
      if (found.rating_question && found.rating_scale) {
        created.push(
          add(found.rating_question, localized(found.rating_scale, language), found.key),
        );
      }
      return json(created, 201);
    }
    const deleting = /^DELETE \/questions\/(.+)$/.exec(route)?.[1];
    if (deleting) {
      const used = Object.values(quality.answers).some((answers) => deleting in answers);
      if (used) return fail("quality.question_in_use", 409);
      quality.questions = quality.questions.filter((q) => q.id !== deleting);
      return new Response(null, { status: 204 });
    }
    if (route === "GET /papers") return json(papers.map(row));
    const paperOf = /^GET \/papers\/([^/]+)$/.exec(route)?.[1];
    if (paperOf) return json(assessment(paperOf));
    const answerOf = /^PUT \/papers\/([^/]+)\/answers\/(.+)$/.exec(route);
    if (answerOf) {
      const [, paperId = "", questionId = ""] = answerOf;
      const input = body as { answer: string | null; note: string | null };
      const answers = (quality.answers[paperId] ??= {});
      if (input.answer === null && !input.note) {
        // Clearing both removes the answer, as the real service does.
        Reflect.deleteProperty(answers, questionId);
      } else {
        answers[questionId] = {
          question_id: questionId,
          answer: input.answer,
          note: input.note,
          updated_at: "2026-11-16T10:00:00+00:00",
        };
      }
      return json(assessment(paperId));
    }
    return fail("http.not_found", 404);
  }

  return quality;
}
