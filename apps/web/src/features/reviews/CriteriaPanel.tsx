// Inclusion and exclusion criteria of the review (Task 25): code, stage and order. In each
// stage's screening the first nine active criteria get the keys 1-9, so moving one renumbers
// them. A criterion a decision cites is archived, never deleted.
import type { TFunction } from "i18next";
import { ArrowDown, ArrowUp, Plus } from "lucide-react";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";

import {
  useAddCriterion,
  useCriteria,
  useDeleteCriterion,
  useReorderCriteria,
  useUpdateCriterion,
  type CriterionKind,
  type CriterionView,
  type ScreeningStage,
} from "./api";

type StageChoice = ScreeningStage | "both";
const stageChoices: StageChoice[] = ["both", "title_abstract", "full_text"];
const stages: ScreeningStage[] = ["title_abstract", "full_text"];

const toStage = (choice: StageChoice): ScreeningStage | null => (choice === "both" ? null : choice);

// Highlight terms are typed as one comma-separated line (Task 32).
const toKeywords = (line: string): string[] =>
  line
    .split(",")
    .map((term) => term.trim())
    .filter(Boolean);

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

export function CriteriaPanel({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const criteria = useCriteria(reviewId);
  const update = useUpdateCriterion(reviewId);
  const remove = useDeleteCriterion(reviewId);
  const reorder = useReorderCriteria(reviewId);
  const all = criteria.data ?? [];
  const active = all.filter((criterion) => !criterion.archived);
  const archived = all.filter((criterion) => criterion.archived);
  const failed = [update, remove, reorder].find((mutation) => mutation.isError);

  function move(index: number, by: -1 | 1) {
    const ids = active.map((criterion) => criterion.id);
    const [moved] = ids.splice(index, 1);
    if (moved === undefined) return;
    ids.splice(index + by, 0, moved);
    reorder.mutate(ids);
  }

  return (
    <section aria-labelledby="review-criteria" className="space-y-2">
      <h2 id="review-criteria" className="text-h3">
        {t("reviews.criteria.title")}
      </h2>
      <p className="text-meta text-fg-muted">{t("reviews.criteria.hint")}</p>
      {criteria.isSuccess && all.length === 0 && (
        <p className="text-ui text-fg-muted">{t("reviews.criteria.empty")}</p>
      )}
      {all.length > 0 && (
        <table className="w-full text-left text-ui">
          <thead className="text-meta text-fg-muted">
            <tr className="border-b border-line">
              {stages.map((stage) => (
                <th key={stage} className="h-row w-12 pr-2 font-normal">
                  <abbr title={t(`reviews.panel.stage.${stage}`)}>
                    {t(`reviews.criteria.keyColumn.${stage}`)}
                  </abbr>
                </th>
              ))}
              <th className="pr-2 font-normal">{t("reviews.criteria.code")}</th>
              <th className="pr-2 font-normal">{t("reviews.criteria.text")}</th>
              <th className="pr-2 font-normal">{t("reviews.criteria.stage")}</th>
              <th className="font-normal">
                <span className="sr-only">{t("reviews.criteria.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {active.map((criterion, index) => (
              <CriterionRow
                key={criterion.id}
                reviewId={reviewId}
                criterion={criterion}
                busy={reorder.isPending}
                onMove={(by) => {
                  move(index, by);
                }}
                first={index === 0}
                last={index === active.length - 1}
                onArchive={() => {
                  update.mutate({ id: criterion.id, archived: true });
                }}
                onDelete={() => {
                  remove.mutate(criterion.id);
                }}
              />
            ))}
            {archived.map((criterion) => (
              <CriterionRow
                key={criterion.id}
                reviewId={reviewId}
                criterion={criterion}
                onRestore={() => {
                  update.mutate({ id: criterion.id, archived: false });
                }}
              />
            ))}
          </tbody>
        </table>
      )}
      {failed && (
        <p role="alert" className="text-meta text-danger">
          {errorText(t, failed.error)}
        </p>
      )}
      <AddCriterion reviewId={reviewId} />
    </section>
  );
}

function ShortcutKey({ value }: { value: number | null }) {
  if (value === null) return <span className="text-fg-muted">—</span>;
  return (
    <kbd className="rounded-xs border border-kbd-line bg-kbd px-1.5 font-mono text-meta">
      {value}
    </kbd>
  );
}

function CriterionRow({
  reviewId,
  criterion,
  busy = false,
  first = false,
  last = false,
  onMove,
  onArchive,
  onDelete,
  onRestore,
}: {
  reviewId: string;
  criterion: CriterionView;
  busy?: boolean;
  first?: boolean;
  last?: boolean;
  onMove?: (by: -1 | 1) => void;
  onArchive?: () => void;
  onDelete?: () => void;
  onRestore?: () => void;
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const code = criterion.code;

  if (editing) {
    return (
      <tr className="border-b border-line">
        <td colSpan={6} className="py-2">
          <CriterionEditor
            reviewId={reviewId}
            criterion={criterion}
            onDone={() => {
              setEditing(false);
            }}
          />
        </td>
      </tr>
    );
  }

  return (
    <tr className={cn("border-b border-line align-top", criterion.archived && "text-fg-muted")}>
      {stages.map((stage) => (
        <td key={stage} className="py-2 pr-2">
          <ShortcutKey value={criterion.shortcuts[stage]} />
        </td>
      ))}
      <td className="py-2 pr-2">
        <span
          className={cn(
            "font-mono text-meta",
            criterion.kind === "inclusion" ? "text-success" : "text-danger",
          )}
        >
          {code}
        </span>
        <span className="sr-only"> {t(`reviews.criteria.kinds.${criterion.kind}`)}</span>
      </td>
      <td className="py-2 pr-2">
        {criterion.text}
        {criterion.archived && (
          <span className="ml-2 text-meta">{t("reviews.criteria.archivedTag")}</span>
        )}
        {criterion.keywords.length > 0 && (
          <p className="text-meta text-fg-muted">
            <span className="sr-only">{t("reviews.criteria.keywords")}: </span>
            {criterion.keywords.join(", ")}
          </p>
        )}
      </td>
      <td className="py-2 pr-2 text-meta text-fg-muted">
        {t(`reviews.criteria.stages.${criterion.stage ?? "both"}`)}
      </td>
      <td className="py-1 text-right whitespace-nowrap">
        {onMove && (
          <>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("reviews.criteria.moveUp", { code })}
              disabled={first || busy}
              onClick={() => {
                onMove(-1);
              }}
            >
              <ArrowUp />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={t("reviews.criteria.moveDown", { code })}
              disabled={last || busy}
              onClick={() => {
                onMove(1);
              }}
            >
              <ArrowDown />
            </Button>
          </>
        )}
        {!criterion.archived && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("reviews.criteria.editLabel", { code })}
            onClick={() => {
              setEditing(true);
            }}
          >
            {t("reviews.criteria.edit")}
          </Button>
        )}
        {criterion.used && onArchive && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("reviews.criteria.archiveLabel", { code })}
            title={t("reviews.criteria.archiveHint")}
            onClick={onArchive}
          >
            {t("reviews.criteria.archive")}
          </Button>
        )}
        {!criterion.used && onDelete && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("reviews.criteria.deleteLabel", { code })}
            onClick={onDelete}
          >
            {t("reviews.criteria.delete")}
          </Button>
        )}
        {onRestore && (
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("reviews.criteria.restoreLabel", { code })}
            onClick={onRestore}
          >
            {t("reviews.criteria.restore")}
          </Button>
        )}
      </td>
    </tr>
  );
}

function StageSelect({
  value,
  onChange,
}: {
  value: StageChoice;
  onChange: (value: StageChoice) => void;
}) {
  const { t } = useTranslation();
  return (
    <select
      aria-label={t("reviews.criteria.stage")}
      className="h-8 rounded-md border border-line-strong bg-raised px-2 text-ui text-fg"
      value={value}
      onChange={(event) => {
        const next = stageChoices.find((choice) => choice === event.target.value);
        if (next) onChange(next);
      }}
    >
      {stageChoices.map((choice) => (
        <option key={choice} value={choice}>
          {t(`reviews.criteria.stages.${choice}`)}
        </option>
      ))}
    </select>
  );
}

function KeywordsInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  return (
    <Input
      aria-label={t("reviews.criteria.keywords")}
      placeholder={t("reviews.criteria.keywordsPlaceholder")}
      title={t("reviews.criteria.keywordsHint")}
      className="min-w-48 basis-full"
      value={value}
      onChange={(event) => {
        onChange(event.target.value);
      }}
    />
  );
}

function CriterionEditor({
  reviewId,
  criterion,
  onDone,
}: {
  reviewId: string;
  criterion: CriterionView;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const update = useUpdateCriterion(reviewId);
  const [code, setCode] = useState(criterion.code);
  const [text, setText] = useState(criterion.text);
  const [stage, setStage] = useState<StageChoice>(criterion.stage ?? "both");
  const [keywords, setKeywords] = useState(criterion.keywords.join(", "));

  function save(event: SyntheticEvent) {
    event.preventDefault();
    if (!code.trim() || !text.trim()) return;
    update.mutate(
      {
        id: criterion.id,
        code: code.trim(),
        text: text.trim(),
        stage: toStage(stage),
        keywords: toKeywords(keywords),
      },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={save} className="flex flex-wrap items-center gap-2">
      <Input
        aria-label={t("reviews.criteria.code")}
        className="w-24 font-mono"
        value={code}
        maxLength={16}
        onChange={(event) => {
          setCode(event.target.value);
        }}
      />
      <Input
        aria-label={t("reviews.criteria.text")}
        className="min-w-48 flex-1"
        value={text}
        maxLength={2000}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      <StageSelect value={stage} onChange={setStage} />
      <KeywordsInput value={keywords} onChange={setKeywords} />
      <Button type="submit" size="sm" variant="primary" disabled={update.isPending}>
        {t("reviews.criteria.save")}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={onDone}>
        {t("reviews.criteria.cancel")}
      </Button>
      {update.isError && (
        <p role="alert" className="basis-full text-meta text-danger">
          {errorText(t, update.error)}
        </p>
      )}
    </form>
  );
}

function AddCriterion({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const add = useAddCriterion(reviewId);
  const [kind, setKind] = useState<CriterionKind>("exclusion");
  const [code, setCode] = useState("");
  const [text, setText] = useState("");
  const [stage, setStage] = useState<StageChoice>("both");
  const [keywords, setKeywords] = useState("");

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    add.mutate(
      {
        kind,
        code: code.trim() || null,
        text: text.trim(),
        stage: toStage(stage),
        keywords: toKeywords(keywords),
      },
      {
        onSuccess: () => {
          setCode("");
          setText("");
          setKeywords("");
        },
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      aria-label={t("reviews.criteria.add")}
      className="flex flex-wrap items-center gap-2 rounded-md border border-line bg-raised p-2"
    >
      <Segmented
        aria-label={t("reviews.criteria.kind")}
        value={kind}
        onValueChange={setKind}
        options={(["inclusion", "exclusion"] as const).map((value) => ({
          value,
          label: t(`reviews.criteria.kinds.${value}`),
        }))}
      />
      <Input
        aria-label={t("reviews.criteria.code")}
        placeholder={t("reviews.criteria.codeAuto")}
        className="w-24 font-mono"
        value={code}
        maxLength={16}
        onChange={(event) => {
          setCode(event.target.value);
        }}
      />
      <Input
        aria-label={t("reviews.criteria.text")}
        placeholder={t("reviews.criteria.textPlaceholder")}
        className="min-w-48 flex-1"
        value={text}
        maxLength={2000}
        onChange={(event) => {
          setText(event.target.value);
        }}
      />
      <StageSelect value={stage} onChange={setStage} />
      <KeywordsInput value={keywords} onChange={setKeywords} />
      <Button type="submit" size="sm" disabled={!text.trim() || add.isPending}>
        <Plus />
        {t("reviews.criteria.add")}
      </Button>
      {add.isError && (
        <p role="alert" className="basis-full text-meta text-danger">
          {errorText(t, add.error)}
        </p>
      )}
    </form>
  );
}
