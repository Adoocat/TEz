// Assessing the studies included at full text: the list on the left (virtualised, with
// derived progress and totals), the selected paper's questions on the right.
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

import {
  formatScore,
  usePaperAssessment,
  useQualityPapers,
  useSaveAnswer,
  type PaperQualityRow,
  type QuestionView,
} from "./api";
import { errorText } from "./QuestionSet";

const rowHeight = 56;

function useNumber() {
  const { i18n } = useTranslation();
  return (value: number) => value.toLocaleString(i18n.language);
}

export function AssessView({
  reviewId,
  questions,
}: {
  reviewId: string;
  questions: QuestionView[];
}) {
  const { t } = useTranslation();
  const papers = useQualityPapers(reviewId);
  const rows = papers.data ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedIndex = rows.findIndex((row) => row.paper_id === selectedId);
  const selected = selectedIndex === -1 ? rows[0] : rows[selectedIndex];

  if (papers.isSuccess && rows.length === 0) {
    return <p className="text-ui text-fg-muted">{t("quality.noPapers")}</p>;
  }
  if (questions.length === 0) {
    return <p className="text-ui text-fg-muted">{t("quality.noQuestionsToAssess")}</p>;
  }
  const at = selected ? rows.indexOf(selected) : -1;
  const go = (index: number) => {
    const row = rows[index];
    if (row) setSelectedId(row.paper_id);
  };

  return (
    <div className="grid min-h-0 gap-4 md:grid-cols-[minmax(16rem,1fr)_2fr]">
      <PaperList rows={rows} selectedId={selected?.paper_id ?? null} onSelect={setSelectedId} />
      {selected && (
        <section aria-label={selected.title} className="min-w-0 space-y-3">
          <header className="space-y-1">
            <h2 className="text-h3">{selected.title}</h2>
            <p className="text-meta text-fg-muted">
              {[selected.first_author, selected.year].filter(Boolean).join(" · ")}
            </p>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                disabled={at <= 0}
                onClick={() => {
                  go(at - 1);
                }}
              >
                <ArrowLeft />
                {t("quality.previous")}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={at >= rows.length - 1}
                onClick={() => {
                  go(at + 1);
                }}
              >
                {t("quality.next")}
                <ArrowRight />
              </Button>
            </div>
          </header>
          <PaperForm
            key={selected.paper_id}
            reviewId={reviewId}
            paperId={selected.paper_id}
            questions={questions}
          />
        </section>
      )}
    </div>
  );
}

function PaperList({
  rows,
  selectedId,
  onSelect,
}: {
  rows: PaperQualityRow[];
  selectedId: string | null;
  onSelect: (paperId: string) => void;
}) {
  const { t } = useTranslation();
  const number = useNumber();
  const scroller = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react-hooks/incompatible-library -- only skips memoizing this component
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => rowHeight,
    overscan: 8,
    getItemKey: (index) => rows[index]?.paper_id ?? index,
  });

  return (
    <div
      ref={scroller}
      className="max-h-[70vh] min-h-0 overflow-auto rounded-md border border-line bg-raised"
    >
      <ul
        aria-label={t("quality.papers")}
        className="relative"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {virtualizer.getVirtualItems().map((item) => {
          const row = rows[item.index];
          if (!row) return null;
          const score = formatScore(row, number);
          const done = row.questions > 0 && row.answered === row.questions;
          return (
            <li
              key={item.key}
              className="absolute inset-x-0"
              style={{ top: item.start, height: rowHeight }}
            >
              <button
                type="button"
                aria-current={row.paper_id === selectedId ? "true" : undefined}
                className={cn(
                  "flex h-full w-full flex-col justify-center gap-0.5 border-b border-line px-3 text-left hover:bg-hovered",
                  row.paper_id === selectedId && "bg-primary-soft",
                )}
                onClick={() => {
                  onSelect(row.paper_id);
                }}
              >
                <span className="w-full truncate text-ui">{row.title}</span>
                <span className="flex gap-2 text-meta text-fg-muted">
                  <span className={done ? "text-success" : undefined}>
                    {t("quality.answeredOf", {
                      answered: number(row.answered),
                      questions: number(row.questions),
                    })}
                  </span>
                  {score && <span>{t("quality.score", { score })}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function PaperForm({
  reviewId,
  paperId,
  questions,
}: {
  reviewId: string;
  paperId: string;
  questions: QuestionView[];
}) {
  const { t } = useTranslation();
  const assessment = usePaperAssessment(reviewId, paperId);
  const save = useSaveAnswer(reviewId, paperId);
  if (!assessment.data) return null;
  const answers = new Map(assessment.data.answers.map((a) => [a.question_id, a]));

  return (
    <div className="space-y-3">
      <ol className="space-y-3">
        {questions.map((question, index) => {
          const current = answers.get(question.id);
          return (
            <QuestionAnswer
              key={`${question.id}:${current?.note ?? ""}`}
              question={question}
              code={t("quality.questionCode", { n: index + 1 })}
              answer={current?.answer ?? null}
              note={current?.note ?? null}
              onSave={(answer, note) => {
                save.mutate({ questionId: question.id, answer, note });
              }}
            />
          );
        })}
      </ol>
      {save.isError && (
        <p role="alert" className="text-meta text-danger">
          {errorText(t, save.error)}
        </p>
      )}
    </div>
  );
}

function QuestionAnswer({
  question,
  code,
  answer,
  note,
  onSave,
}: {
  question: QuestionView;
  code: string;
  answer: string | null;
  note: string | null;
  onSave: (answer: string | null, note: string | null) => void;
}) {
  const { t } = useTranslation();
  // Keyed by the saved note, so a saved change resets the draft.
  const [draft, setDraft] = useState(note ?? "");

  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <fieldset className="space-y-2">
        <legend className="flex gap-2 text-ui">
          <span className="shrink-0 font-mono text-meta text-fg-muted">{code}</span>
          <span>{question.text}</span>
        </legend>
        {question.guidance && (
          <p className="text-meta whitespace-pre-line text-fg-muted">{question.guidance}</p>
        )}
        <div className="flex flex-wrap gap-1.5">
          {question.scale.map((option) => (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 text-ui",
                option.value === answer && "border-primary bg-primary-soft",
              )}
            >
              <input
                type="radio"
                className="size-3.5"
                name={question.id}
                checked={option.value === answer}
                onChange={() => {
                  onSave(option.value, note);
                }}
              />
              {option.label}
            </label>
          ))}
          {answer !== null && (
            <Button
              size="sm"
              variant="ghost"
              aria-label={t("quality.clearAnswer", { code })}
              onClick={() => {
                onSave(null, note);
              }}
            >
              {t("quality.clear")}
            </Button>
          )}
        </div>
      </fieldset>
      <textarea
        aria-label={t("quality.noteFor", { code })}
        placeholder={t("quality.notePlaceholder")}
        className="w-full rounded-md border border-line-strong bg-raised p-2 text-meta text-fg placeholder:text-fg-muted"
        rows={1}
        maxLength={4000}
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        onBlur={() => {
          if (draft.trim() !== (note ?? "")) onSave(answer, draft.trim() || null);
        }}
      />
    </li>
  );
}
