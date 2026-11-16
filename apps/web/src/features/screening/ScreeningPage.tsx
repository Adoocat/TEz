// Screening (design 5.2, Task 32): one record at a time in focus mode, or a table in list
// mode. Decisions go to the backend's append-only screening service; the screen moves on at
// once from the cached queue and confirms when the backend answers.
import { useVirtualizer } from "@tanstack/react-virtual";
import type { TFunction } from "i18next";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { useReviews } from "@/features/reviews/api";
import { useActiveReview } from "@/features/reviews/store";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";
import { ariaShortcut, ShortcutKeys } from "@/lib/shortcuts/ShortcutKeys";
import { useShortcuts } from "@/lib/shortcuts/useShortcuts";

import {
  useDecide,
  usePrefetchRecords,
  useQueue,
  useRecord,
  useStageCriteria,
  useUndo,
  type ChosenDecision,
  type ScreeningStage,
  type StageCriterion,
} from "./api";
import { CriteriaSidebar } from "./CriteriaSidebar";
import { DecisionBar } from "./DecisionBar";
import { NoteDialog } from "./NoteDialog";
import { matches, step, type QueueFilter, type QueueItem } from "./queue";
import { RecordView } from "./RecordView";
import { StateBadge } from "./StateBadge";
import { useScreeningSession } from "./store";

const stages: ScreeningStage[] = ["title_abstract", "full_text"];
const filtersFor = (stage: ScreeningStage): QueueFilter[] =>
  stage === "full_text"
    ? ["undecided", "maybe", "include", "exclude", "not_retrieved", "all"]
    : ["undecided", "maybe", "include", "exclude", "all"];

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

export function ScreeningPage() {
  const { t } = useTranslation();
  const reviews = useReviews();
  const review = useActiveReview();
  if (reviews.isPending) return null;
  if (!review) {
    return (
      <div className="p-6 text-ui">
        <h1 className="text-h2">{t("nav.screening")}</h1>
        <p className="mt-2 text-fg-muted">
          {t("screening.noReview")}{" "}
          <Link to="/review" className="text-primary underline">
            {t("screening.toReview")}
          </Link>
        </p>
      </div>
    );
  }
  return <Screening key={review.id} reviewId={review.id} />;
}

function Screening({ reviewId }: { reviewId: string }) {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const stage: ScreeningStage =
    params.get("stage") === "full_text" ? "full_text" : "title_abstract";
  const mode = params.get("mode") === "list" ? "list" : "focus";
  const filter: QueueFilter =
    filtersFor(stage).find((f) => f === params.get("filter")) ?? "undecided";
  function setParam(key: string, value: string) {
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        next.set(key, value);
        return next;
      },
      { replace: true },
    );
  }

  const queue = useQueue(reviewId, stage);
  const criteria = useStageCriteria(reviewId, stage);
  const decide = useDecide(reviewId, stage);
  const undo = useUndo(reviewId, stage);
  const prefetch = usePrefetchRecords(reviewId, stage);
  const session = useScreeningSession();
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [excludeOpen, setExcludeOpen] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const items = queue.data?.items ?? [];
  const shown = items.filter((item) => matches(item, filter));
  // The record on screen stays put after a decision until we move; at first, or when it
  // left the queue, the first one the filter shows.
  const current: QueueItem | undefined =
    items.find((item) => item.paper_id === chosenId) ?? shown[0];
  const currentId = current?.paper_id ?? null;
  const record = useRecord(reviewId, stage, currentId);
  // A record from the cache is shown only if it is the current one.
  const shownRecord = record.data?.paper_id === currentId ? record.data : undefined;
  const stageCriteria = criteria.data ?? [];
  const exclusions = stageCriteria.filter((c) => c.kind === "exclusion");

  const nextId = step(items, currentId, 1, filter)?.paper_id;
  const previousId = step(items, currentId, -1, filter)?.paper_id;
  useEffect(() => {
    prefetch([nextId, previousId]);
    // `prefetch` is a new function each render; the ids are what matter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextId, previousId]);

  function go(direction: 1 | -1) {
    const target = step(items, currentId, direction, filter);
    if (target) setChosenId(target.paper_id);
  }

  function choose(decision: ChosenDecision, criterion: StageCriterion | null = null) {
    if (!current) return;
    const paperId = current.paper_id;
    const note = session.pendingNotes[paperId] ?? record.data?.decision?.note ?? null;
    // Move on at once; the queue cache takes the decision when the backend confirms it.
    const after = step(items, paperId, 1, filter);
    setChosenId(after?.paper_id ?? paperId);
    setExcludeOpen(false);
    setProblem(null);
    decide.mutate(
      { paperId, decision, criterionId: criterion?.id ?? null, note },
      {
        onSuccess: (made) => {
          session.remember({ reviewId, stage, paperId, decisionId: made.id });
          session.setPendingNote(paperId, null);
          // Nothing else in this view: the empty state says so.
          if (!after) setChosenId(null);
        },
        onError: (error) => {
          setChosenId(paperId);
          setProblem(errorText(t, error));
        },
      },
    );
  }

  function byCriterion(criterion: StageCriterion) {
    choose(criterion.kind === "inclusion" ? "include" : "exclude", criterion);
  }

  function takeBack() {
    const last = session.takeBack(reviewId, stage);
    if (!last) {
      setProblem(t("screening.nothingToUndo"));
      return;
    }
    setProblem(null);
    setChosenId(last.paperId);
    undo.mutate(last.decisionId, {
      onError: (error) => {
        setProblem(errorText(t, error));
      },
    });
  }

  function saveNote(note: string) {
    setNoteOpen(false);
    if (!current) return;
    const decided = record.data?.decision;
    if (decided && decided.decision !== "undecided") {
      // A note on a decided record is the same decision again, with the note (a new row).
      decide.mutate(
        {
          paperId: current.paper_id,
          decision: decided.decision,
          criterionId: decided.criterion_id,
          note: note || null,
        },
        {
          onError: (error) => {
            setProblem(errorText(t, error));
          },
        },
      );
    } else {
      session.setPendingNote(current.paper_id, note || null);
    }
  }

  const busy = decide.isPending || undo.isPending;
  const canDecide = current !== undefined;
  useShortcuts(
    "screening",
    {
      include: () => {
        choose("include");
      },
      exclude: () => {
        if (canDecide) setExcludeOpen(true);
      },
      reason: (event) => {
        const criterion = stageCriteria.find((c) => c.shortcut === Number(event.key));
        if (criterion && canDecide) byCriterion(criterion);
      },
      maybe: () => {
        choose("maybe");
      },
      skip: () => {
        go(1);
      },
      next: () => {
        go(1);
      },
      previous: () => {
        go(-1);
      },
      undo: takeBack,
      note: () => {
        if (canDecide) setNoteOpen(true);
      },
    },
    { enabled: !noteOpen },
  );

  const counts = queue.data?.counts;
  const number = new Intl.NumberFormat(i18n.language);
  const percent = new Intl.NumberFormat(i18n.language, { style: "percent" });
  const decidedCount = counts ? counts.total - counts.undecided : 0;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-2">
        <nav aria-label={t("screening.stages")} className="flex gap-1">
          {stages.map((s) => (
            <Link
              key={s}
              to={`/screening?stage=${s}`}
              aria-current={s === stage ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1 text-ui",
                s === stage ? "bg-primary-soft text-primary" : "text-fg-muted hover:bg-hovered",
              )}
            >
              {t(`reviews.panel.stage.${s}`)}
            </Link>
          ))}
        </nav>
        {counts && (
          <p className="text-meta text-fg-muted tabular-nums" aria-live="polite">
            {t("screening.progress", {
              decided: number.format(decidedCount),
              total: number.format(counts.total),
              percent: percent.format(counts.total ? decidedCount / counts.total : 0),
            })}
          </p>
        )}
        <p className="rounded-xs border border-line px-1.5 font-mono text-meta">
          {t("screening.session", { count: session.decided })}
        </p>
        <div className="flex-1" />
        <label className="flex items-center gap-1 text-meta text-fg-muted">
          {t("screening.filter.label")}
          <select
            className="h-8 rounded-md border border-line-strong bg-raised px-2 text-ui text-fg"
            value={filter}
            onChange={(event) => {
              setParam("filter", event.target.value);
              setChosenId(null);
            }}
          >
            {filtersFor(stage).map((f) => (
              <option key={f} value={f}>
                {t(`screening.filter.${f}`, {
                  n: number.format(f === "all" ? (counts?.total ?? 0) : (counts?.[f] ?? 0)),
                })}
              </option>
            ))}
          </select>
        </label>
        <Segmented
          aria-label={t("screening.mode.label")}
          value={mode}
          onValueChange={(value) => {
            setParam("mode", value);
          }}
          options={[
            { value: "focus", label: t("screening.mode.focus") },
            { value: "list", label: t("screening.mode.list") },
          ]}
        />
      </header>
      {problem && (
        <p
          role="alert"
          className="border-b border-line bg-raised px-4 py-1.5 text-meta text-danger"
        >
          {problem}
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-y-auto">
          {queue.isPending ? null : queue.isError ? (
            <p role="alert" className="p-6 text-ui text-danger">
              {errorText(t, queue.error)}
            </p>
          ) : items.length === 0 ? (
            <Empty title={t("screening.empty.noRecords")} />
          ) : mode === "list" ? (
            <ListView
              items={shown}
              currentId={currentId}
              criteria={stageCriteria}
              onSelect={setChosenId}
              onOpen={(paperId) => {
                setChosenId(paperId);
                setParam("mode", "focus");
              }}
            />
          ) : !current ? (
            <Empty
              title={t("screening.empty.filterDone")}
              action={
                filter !== "all" && (
                  <Button
                    onClick={() => {
                      setParam("filter", "all");
                    }}
                  >
                    {t("screening.empty.showAll")}
                  </Button>
                )
              }
            />
          ) : (
            <div className="space-y-4 px-6 py-4">
              <div className="mx-auto flex max-w-3xl items-center justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  aria-keyshortcuts={ariaShortcut("screening", "previous")}
                  disabled={!previousId || previousId === currentId}
                  onClick={() => {
                    go(-1);
                  }}
                >
                  <ArrowLeft aria-hidden />
                  {t("screening.previous")}
                  <ShortcutKeys context="screening" id="previous" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-keyshortcuts={ariaShortcut("screening", "next")}
                  disabled={!nextId || nextId === currentId}
                  onClick={() => {
                    go(1);
                  }}
                >
                  {t("screening.next")}
                  <ShortcutKeys context="screening" id="next" />
                  <ArrowRight aria-hidden />
                </Button>
              </div>
              {shownRecord ? (
                <RecordView
                  record={shownRecord}
                  criteria={stageCriteria}
                  pendingNote={session.pendingNotes[current.paper_id]}
                />
              ) : (
                <div aria-busy className="mx-auto max-w-3xl">
                  <h1 className="font-serif text-h1">{current.title}</h1>
                </div>
              )}
            </div>
          )}
        </main>
        <CriteriaSidebar
          criteria={stageCriteria}
          chosenId={current?.criterion_id}
          disabled={!canDecide}
          onChoose={byCriterion}
        />
      </div>
      <DecisionBar
        exclusions={exclusions}
        excludeOpen={excludeOpen}
        onExcludeOpenChange={setExcludeOpen}
        busy={busy}
        canDecide={canDecide}
        fullText={stage === "full_text"}
        onInclude={() => {
          choose("include");
        }}
        onExclude={byCriterion}
        onMaybe={() => {
          choose("maybe");
        }}
        onNotRetrieved={() => {
          choose("not_retrieved");
        }}
        onSkip={() => {
          go(1);
        }}
        onUndo={takeBack}
        onNote={() => {
          setNoteOpen(true);
        }}
      />
      <NoteDialog
        open={noteOpen}
        initial={
          (current && session.pendingNotes[current.paper_id]) ?? record.data?.decision?.note ?? ""
        }
        onSave={saveNote}
        onClose={() => {
          setNoteOpen(false);
        }}
      />
    </div>
  );
}

function Empty({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="grid h-full place-items-center p-6 text-center">
      <div className="space-y-3">
        <p className="text-ui text-fg-muted">{title}</p>
        {action}
      </div>
    </div>
  );
}

const ROW_HEIGHT = 36;

/** List mode: the filter's records as a table; arrows move, letters decide on the row,
 * Enter opens it in focus mode. */
function ListView({
  items,
  currentId,
  criteria,
  onSelect,
  onOpen,
}: {
  items: readonly QueueItem[];
  currentId: string | null;
  criteria: readonly StageCriterion[];
  onSelect: (paperId: string) => void;
  onOpen: (paperId: string) => void;
}) {
  const { t } = useTranslation();
  const scroller = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react-hooks/incompatible-library -- the virtualizer keeps its own state
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });
  const index = items.findIndex((item) => item.paper_id === currentId);

  function move(by: 1 | -1) {
    const target = items[Math.min(Math.max(index + by, 0), items.length - 1)];
    if (!target) return;
    onSelect(target.paper_id);
    virtualizer.scrollToIndex(items.indexOf(target));
  }
  useShortcuts("list", {
    down: () => {
      move(1);
    },
    up: () => {
      move(-1);
    },
    open: () => {
      if (currentId) onOpen(currentId);
    },
  });

  if (items.length === 0) return <Empty title={t("screening.empty.filterDone")} />;
  return (
    <div
      ref={scroller}
      role="table"
      aria-label={t("screening.list.label")}
      aria-rowcount={items.length}
      className="h-full overflow-auto text-ui"
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((row) => {
          const item = items[row.index];
          if (!item) return null;
          const code = criteria.find((c) => c.id === item.criterion_id)?.code;
          return (
            <div
              key={item.paper_id}
              role="row"
              aria-selected={item.paper_id === currentId}
              aria-rowindex={row.index + 1}
              onClick={() => {
                onSelect(item.paper_id);
              }}
              onDoubleClick={() => {
                onOpen(item.paper_id);
              }}
              style={{ height: ROW_HEIGHT, transform: `translateY(${String(row.start)}px)` }}
              className={cn(
                "absolute inset-x-0 top-0 flex items-center gap-3 border-b border-line px-4",
                item.paper_id === currentId ? "bg-primary-soft" : "hover:bg-hovered",
              )}
            >
              <span role="cell" className="w-12 shrink-0 text-meta text-fg-muted tabular-nums">
                {item.position}
              </span>
              <span role="cell" className="min-w-0 flex-1 truncate" title={item.title}>
                {item.title}
              </span>
              <span role="cell" className="w-40 shrink-0 truncate text-meta text-fg-muted">
                {[item.first_author, item.year].filter(Boolean).join(" · ")}
              </span>
              <span role="cell" className="w-36 shrink-0">
                <StateBadge state={item.state} code={code} />
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
