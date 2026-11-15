// Creating a review (design 4.1's stepper): title and method, research questions, protocol
// note. Only the title is required, so the review can be created from any step.
import { Plus, X } from "lucide-react";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/cn";

import { reviewMethods, useCreateReview, type ReviewMethod, type ReviewView } from "./api";
import { useActiveReviewStore } from "./store";

const steps = ["basics", "questions", "protocol"] as const;
const maxQuestions = 20;

interface Question {
  key: number;
  text: string;
}

let nextKey = 0;
const blankQuestion = (): Question => ({ key: nextKey++, text: "" });

export function ReviewWizard({ onCreated }: { onCreated?: (review: ReviewView) => void }) {
  const { t } = useTranslation();
  const create = useCreateReview();
  const setActiveReview = useActiveReviewStore((state) => state.setActiveReview);
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState("");
  const [method, setMethod] = useState<ReviewMethod>("prisma2020");
  const [questions, setQuestions] = useState<Question[]>(() => [blankQuestion()]);
  const [protocol, setProtocol] = useState("");
  const last = step === steps.length - 1;

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    create.mutate(
      {
        title: trimmed,
        method,
        research_questions: questions.map((q) => q.text.trim()).filter(Boolean),
        protocol: protocol.trim() || null,
      },
      {
        onSuccess: (review) => {
          setActiveReview(review.id);
          setTitle("");
          setQuestions([blankQuestion()]);
          setProtocol("");
          setStep(0);
          onCreated?.(review);
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <ol className="grid grid-cols-3 gap-2" aria-label={t("reviews.wizard.steps")}>
        {steps.map((name, index) => (
          <li key={name}>
            <button
              type="button"
              aria-current={index === step ? "step" : undefined}
              className="w-full space-y-1 text-left"
              onClick={() => {
                setStep(index);
              }}
            >
              <span
                className={cn(
                  "block h-1 rounded-full",
                  index <= step ? "bg-primary" : "bg-line-strong",
                )}
              />
              <span
                className={cn(
                  "block font-mono text-meta",
                  index === step ? "text-fg" : "text-fg-muted",
                )}
              >
                {String(index + 1)}. {t(`reviews.wizard.step.${name}`)}
              </span>
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-meta text-fg-muted">{t("reviews.titleLabel")}</span>
            <Input
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
              }}
              placeholder={t("reviews.titlePlaceholder")}
              maxLength={300}
            />
          </label>
          <div className="space-y-1">
            <span className="block text-meta text-fg-muted">{t("reviews.methodLabel")}</span>
            <Segmented
              aria-label={t("reviews.methodLabel")}
              value={method}
              onValueChange={setMethod}
              options={reviewMethods.map((value) => ({
                value,
                label: t(`reviews.methods.${value}`),
              }))}
            />
            <p className="text-meta text-fg-muted">{t(`reviews.methodHint.${method}`)}</p>
          </div>
        </div>
      )}

      {step === 1 && (
        <fieldset className="space-y-2">
          <legend className="text-meta text-fg-muted">{t("reviews.wizard.questionsHint")}</legend>
          {questions.map((question, index) => {
            const label = t("reviews.questionLabel", { n: index + 1 });
            return (
              <div key={question.key} className="flex items-center gap-2">
                <span className="w-9 shrink-0 font-mono text-meta text-fg-muted">
                  {t("reviews.questionCode", { n: index + 1 })}
                </span>
                <Input
                  aria-label={label}
                  value={question.text}
                  maxLength={1000}
                  onChange={(event) => {
                    const text = event.target.value;
                    setQuestions(questions.map((q, i) => (i === index ? { ...q, text } : q)));
                  }}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t("reviews.removeQuestion", { n: index + 1 })}
                  disabled={questions.length === 1}
                  onClick={() => {
                    setQuestions(questions.filter((_, i) => i !== index));
                  }}
                >
                  <X />
                </Button>
              </div>
            );
          })}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={questions.length >= maxQuestions}
            onClick={() => {
              setQuestions([...questions, blankQuestion()]);
            }}
          >
            <Plus />
            {t("reviews.addQuestion")}
          </Button>
        </fieldset>
      )}

      {step === 2 && (
        <label className="block space-y-1">
          <span className="text-meta text-fg-muted">{t("reviews.protocolLabel")}</span>
          <textarea
            value={protocol}
            maxLength={20_000}
            rows={6}
            placeholder={t("reviews.protocolPlaceholder")}
            onChange={(event) => {
              setProtocol(event.target.value);
            }}
            className="w-full rounded-md border border-line-strong bg-raised px-2.5 py-1.5 text-ui text-fg placeholder:text-fg-muted"
          />
        </label>
      )}

      {create.isError && (
        <p role="alert" className="text-meta text-danger">
          {t("reviews.createFailed")}
        </p>
      )}
      <div className="flex items-center gap-2">
        {step > 0 && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setStep(step - 1);
            }}
          >
            {t("reviews.wizard.back")}
          </Button>
        )}
        <div className="flex-1" />
        {!last && (
          <Button
            type="button"
            onClick={() => {
              setStep(step + 1);
            }}
          >
            {t("reviews.wizard.next")}
          </Button>
        )}
        <Button type="submit" variant="primary" disabled={!title.trim() || create.isPending}>
          {t("reviews.create")}
        </Button>
      </div>
    </form>
  );
}
