// The review's question set: its own questions with any scale, pasted lists, and bundled
// templates whose license allows it (ADR 0026). Nothing here assumes one field or tool.
import type { TFunction } from "i18next";
import { ArrowDown, ArrowUp, Pencil, Trash2 } from "lucide-react";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";

import {
  useAddQuestions,
  useApplyTemplate,
  useDeleteQuestion,
  useQualityCatalog,
  useReorderQuestions,
  useUpdateQuestion,
  type QuestionView,
  type ScaleOption,
  type TemplateView,
} from "./api";
import { presetOptions, ScaleEditor, scaleIsValid, uiLanguage } from "./ScaleEditor";

const defaultPreset = "yes_partly_no";
const custom = "custom";

export function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

const areaClass =
  "w-full rounded-md border border-line-strong bg-raised p-2 text-ui text-fg placeholder:text-fg-muted";

export function QuestionSet({
  reviewId,
  questions,
}: {
  reviewId: string;
  questions: QuestionView[];
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      <section aria-labelledby="quality-questions" className="space-y-2">
        <h2 id="quality-questions" className="text-h3">
          {t("quality.questions")}
        </h2>
        {questions.length === 0 ? (
          <p className="text-ui text-fg-muted">{t("quality.noQuestions")}</p>
        ) : (
          <QuestionList reviewId={reviewId} questions={questions} />
        )}
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <AddQuestions reviewId={reviewId} />
        <Templates reviewId={reviewId} />
      </div>
    </div>
  );
}

function QuestionList({ reviewId, questions }: { reviewId: string; questions: QuestionView[] }) {
  const { t } = useTranslation();
  const reorder = useReorderQuestions(reviewId);
  const remove = useDeleteQuestion(reviewId);
  const [editing, setEditing] = useState<string | null>(null);

  function move(index: number, by: 1 | -1) {
    const ids = questions.map((q) => q.id);
    const [moved] = ids.splice(index, 1);
    if (moved === undefined) return;
    ids.splice(index + by, 0, moved);
    reorder.mutate(ids);
  }

  return (
    <div className="space-y-2">
      <ol className="divide-y divide-line rounded-md border border-line bg-raised">
        {questions.map((question, index) => {
          const code = t("quality.questionCode", { n: index + 1 });
          return (
            <li key={question.id} className="space-y-2 p-3">
              {editing === question.id ? (
                <QuestionEditor
                  reviewId={reviewId}
                  question={question}
                  code={code}
                  onDone={() => {
                    setEditing(null);
                  }}
                />
              ) : (
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 shrink-0 rounded-xs bg-primary-soft px-1.5 font-mono text-meta">
                    {code}
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="text-ui">{question.text}</p>
                    {question.guidance && (
                      <p className="text-meta whitespace-pre-line text-fg-muted">
                        {question.guidance}
                      </p>
                    )}
                    <p className="flex flex-wrap gap-1 text-meta text-fg-muted">
                      {question.scale.map((option) => (
                        <span key={option.value} className="rounded-xs border border-line px-1.5">
                          {option.label}
                          {option.score !== null && ` · ${String(option.score)}`}
                        </span>
                      ))}
                      {question.template && (
                        <span className="px-1.5">{t("quality.fromTemplate")}</span>
                      )}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-0.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("quality.moveUp", { code })}
                      disabled={index === 0 || reorder.isPending}
                      onClick={() => {
                        move(index, -1);
                      }}
                    >
                      <ArrowUp />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("quality.moveDown", { code })}
                      disabled={index === questions.length - 1 || reorder.isPending}
                      onClick={() => {
                        move(index, 1);
                      }}
                    >
                      <ArrowDown />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("quality.edit", { code })}
                      onClick={() => {
                        setEditing(question.id);
                      }}
                    >
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("quality.delete", { code })}
                      disabled={remove.isPending}
                      onClick={() => {
                        remove.mutate(question.id);
                      }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {remove.isError && (
        <p role="alert" className="text-meta text-danger">
          {errorText(t, remove.error)}
        </p>
      )}
    </div>
  );
}

function QuestionEditor({
  reviewId,
  question,
  code,
  onDone,
}: {
  reviewId: string;
  question: QuestionView;
  code: string;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateQuestion(reviewId);
  const [text, setText] = useState(question.text);
  const [guidance, setGuidance] = useState(question.guidance ?? "");
  const [scale, setScale] = useState<ScaleOption[]>(question.scale);
  const valid = text.trim() !== "" && scaleIsValid(scale);

  function save(event: SyntheticEvent) {
    event.preventDefault();
    if (!valid) return;
    update.mutate(
      {
        id: question.id,
        patch: { text: text.trim(), guidance: guidance.trim() || null, scale: { options: scale } },
      },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={save} className="space-y-2" aria-label={t("quality.edit", { code })}>
      <label className="block space-y-1">
        <span className="text-meta text-fg-muted">{t("quality.questionText")}</span>
        <Input
          value={text}
          maxLength={2000}
          onChange={(event) => {
            setText(event.target.value);
          }}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-meta text-fg-muted">{t("quality.guidance")}</span>
        <textarea
          className={areaClass}
          rows={2}
          maxLength={4000}
          value={guidance}
          onChange={(event) => {
            setGuidance(event.target.value);
          }}
        />
      </label>
      <fieldset className="space-y-1">
        <legend className="text-meta text-fg-muted">{t("quality.scale.title")}</legend>
        <ScaleEditor options={scale} onChange={setScale} />
      </fieldset>
      {update.isError && (
        <p role="alert" className="text-meta text-danger">
          {errorText(t, update.error)}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={!valid || update.isPending}>
          {t("quality.save")}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          {t("quality.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** One question or a pasted list (one per line), all with the same scale. */
function AddQuestions({ reviewId }: { reviewId: string }) {
  const { t, i18n } = useTranslation();
  const catalog = useQualityCatalog();
  const add = useAddQuestions(reviewId);
  const [text, setText] = useState("");
  const [preset, setPreset] = useState(defaultPreset);
  const [scale, setScale] = useState<ScaleOption[] | null>(null);
  const language = uiLanguage(i18n.language);
  const presets = catalog.data?.scales ?? [];
  const chosen = presets.find((p) => p.key === preset);
  // Until the user edits it, the scale follows the chosen preset (and the UI language).
  const options =
    scale ?? (chosen ? presetOptions(chosen, language) : blankScale(t("quality.scale.option")));
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "");
  const valid = lines.length > 0 && lines.length <= 200 && scaleIsValid(options);

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!valid) return;
    add.mutate(
      lines.map((line) => ({ text: line, scale: { options } })),
      {
        onSuccess: () => {
          setText("");
        },
      },
    );
  }

  return (
    <section aria-labelledby="quality-add" className="space-y-2">
      <h2 id="quality-add" className="text-h3">
        {t("quality.addTitle")}
      </h2>
      <form onSubmit={submit} className="space-y-3 rounded-md border border-line p-3">
        <label className="block space-y-1">
          <span className="text-meta text-fg-muted">{t("quality.newQuestions")}</span>
          <textarea
            className={areaClass}
            rows={4}
            value={text}
            placeholder={t("quality.newQuestionsPlaceholder")}
            onChange={(event) => {
              setText(event.target.value);
            }}
          />
        </label>
        <p className="text-meta text-fg-muted">{t("quality.pasteHint")}</p>
        <label className="block space-y-1">
          <span className="text-meta text-fg-muted">{t("quality.scale.startFrom")}</span>
          <select
            className="h-8 w-full rounded-md border border-line-strong bg-raised px-2 text-ui text-fg"
            value={preset}
            onChange={(event) => {
              setPreset(event.target.value);
              setScale(null);
            }}
          >
            {presets.map((p) => (
              <option key={p.key} value={p.key}>
                {presetOptions(p, language)
                  .map((o) => o.label)
                  .join(" / ")}
              </option>
            ))}
            <option value={custom}>{t("quality.scale.custom")}</option>
          </select>
        </label>
        <fieldset className="space-y-1">
          <legend className="text-meta text-fg-muted">{t("quality.scale.title")}</legend>
          <ScaleEditor options={options} onChange={setScale} />
        </fieldset>
        {add.isError && (
          <p role="alert" className="text-meta text-danger">
            {errorText(t, add.error)}
          </p>
        )}
        <Button type="submit" variant="primary" disabled={!valid || add.isPending}>
          {t("quality.addQuestions", { count: Math.max(lines.length, 1) })}
        </Button>
      </form>
    </section>
  );
}

function blankScale(label: string): ScaleOption[] {
  return [
    { value: "o1", label: `${label} 1`, score: null },
    { value: "o2", label: `${label} 2`, score: null },
  ];
}

function Templates({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const catalog = useQualityCatalog();
  return (
    <section aria-labelledby="quality-templates" className="space-y-2">
      <h2 id="quality-templates" className="text-h3">
        {t("quality.templates")}
      </h2>
      <p className="text-meta text-fg-muted">{t("quality.templatesHint")}</p>
      <ul className="space-y-2">
        {catalog.data?.templates.map((template) => (
          <TemplateItem key={template.key} reviewId={reviewId} template={template} />
        ))}
      </ul>
    </section>
  );
}

function TemplateItem({ reviewId, template }: { reviewId: string; template: TemplateView }) {
  const { t, i18n } = useTranslation();
  const { platform } = useBackend();
  const apply = useApplyTemplate(reviewId);
  const count = template.questions.length + (template.rating_question ? 1 : 0);

  return (
    <li className="space-y-1.5 rounded-md border border-line bg-raised p-3">
      <p className="text-ui font-medium">{template.title}</p>
      <p className="text-meta text-fg-muted">
        {t(`quality.designs.${template.design}`, { defaultValue: template.design })}
        {" · "}
        {template.publisher}
        {" · "}
        {template.version}
      </p>
      <p className="text-meta text-fg-muted">
        {template.license}
        {" · "}
        <a
          href={template.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-primary hover:underline"
          onClick={(event) => {
            event.preventDefault();
            void platform.openExternal(template.source_url);
          }}
        >
          {t("quality.source")}
        </a>
      </p>
      <details className="text-meta">
        <summary className="cursor-pointer text-fg-muted">
          {t("quality.preview", { count, n: count })}
        </summary>
        <ol className="mt-1 list-decimal space-y-0.5 pl-5">
          {template.questions.map((question) => (
            <li key={question}>{question}</li>
          ))}
          {template.rating_question && <li>{template.rating_question}</li>}
        </ol>
      </details>
      {apply.isError && (
        <p role="alert" className="text-meta text-danger">
          {errorText(t, apply.error)}
        </p>
      )}
      <Button
        size="sm"
        disabled={apply.isPending}
        aria-label={t("quality.useTemplateNamed", { title: template.title })}
        onClick={() => {
          apply.mutate({ template: template.key, language: uiLanguage(i18n.language) });
        }}
      >
        {t("quality.useTemplate", { count, n: count })}
      </Button>
    </li>
  );
}
