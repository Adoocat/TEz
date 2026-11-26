// Editing one cell, in place (Task 52). Text and numbers are typed; choices and yes/no are
// picked. Enter keeps and goes down, Tab keeps and goes right, Escape drops the edit.
import { useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import type { CellValue, CellView, ColumnView } from "./api";
import { editText, parseInput } from "./values";

export type EditResult =
  { kind: "keep"; value: CellValue; then: "down" | "right" | "stay" } | { kind: "cancel" };

const box =
  "absolute inset-0 z-[var(--z-popover)] w-full border-2 border-primary bg-raised px-2.5 text-ui text-fg outline-none";

export function CellEditor({
  column,
  cell,
  start,
  onDone,
}: {
  column: ColumnView;
  cell: CellView | undefined;
  /** The key that started the edit, typed over the old value; null keeps the old value. */
  start: string | null;
  onDone: (result: EditResult) => void;
}) {
  switch (column.data_type) {
    case "text":
    case "number":
      return <TextEditor column={column} cell={cell} start={start} onDone={onDone} />;
    case "enum":
    case "bool":
      return <ChoiceEditor column={column} cell={cell} onDone={onDone} />;
    case "multi_enum":
      return <ChoicesEditor column={column} cell={cell} onDone={onDone} />;
  }
}

/** The edit ends once: leaving the editor after Enter must not keep it a second time. */
function useOnce(onDone: (result: EditResult) => void) {
  const done = useRef(false);
  return (result: EditResult) => {
    if (done.current) return;
    done.current = true;
    onDone(result);
  };
}

/** Where Enter and Tab go after keeping the edit. */
function nextOf(event: KeyboardEvent): "down" | "right" | null {
  if (event.key === "Enter" && !event.shiftKey) return "down";
  if (event.key === "Tab") return "right";
  return null;
}

function TextEditor({
  column,
  cell,
  start,
  onDone,
}: {
  column: ColumnView;
  cell: CellView | undefined;
  start: string | null;
  onDone: (result: EditResult) => void;
}) {
  const finish = useOnce(onDone);
  const { t, i18n } = useTranslation();
  const [text, setText] = useState(() => start ?? editText(column, cell, i18n.language));
  const [invalid, setInvalid] = useState(false);
  const keep = (then: "down" | "right" | "stay") => {
    const parsed = parseInput(column, text, i18n.language);
    if (!parsed.ok) {
      setInvalid(true);
      return;
    }
    finish({ kind: "keep", value: parsed.value, then });
  };
  return (
    <>
      <input
        autoFocus
        aria-label={t("matrix.editCell", { name: column.name })}
        aria-invalid={invalid || undefined}
        inputMode={column.data_type === "number" ? "decimal" : undefined}
        className={box}
        value={text}
        onFocus={(event) => {
          if (start === null) event.currentTarget.select();
        }}
        onChange={(event) => {
          setText(event.target.value);
          setInvalid(false);
        }}
        onKeyDown={(event) => {
          event.stopPropagation();
          const then = nextOf(event);
          if (then) {
            event.preventDefault();
            keep(then);
          } else if (event.key === "Escape") {
            event.preventDefault();
            finish({ kind: "cancel" });
          }
        }}
        onBlur={() => {
          const parsed = parseInput(column, text, i18n.language);
          finish(
            parsed.ok ? { kind: "keep", value: parsed.value, then: "stay" } : { kind: "cancel" },
          );
        }}
      />
      {invalid && (
        <p
          role="alert"
          className="absolute top-full left-0 z-[var(--z-popover)] mt-1 rounded-xs border border-line bg-raised px-2 py-1 text-meta text-danger shadow-popover"
        >
          {t("matrix.notANumber")}
        </p>
      )}
    </>
  );
}

/** One choice, or yes/no: a list to pick from, empty at the top. */
function ChoiceEditor({
  column,
  cell,
  onDone,
}: {
  column: ColumnView;
  cell: CellView | undefined;
  onDone: (result: EditResult) => void;
}) {
  const finish = useOnce(onDone);
  const { t } = useTranslation();
  const bool = column.data_type === "bool";
  const choices = bool
    ? [
        { id: "true", label: t("matrix.yes") },
        { id: "false", label: t("matrix.no") },
      ]
    : column.options;
  const initial = cell?.kept_text != null || cell?.value == null ? "" : String(cell.value);
  const [picked, setPicked] = useState(initial);
  const valueOf = (id: string): CellValue => (id === "" ? null : bool ? id === "true" : id);
  return (
    <select
      autoFocus
      aria-label={t("matrix.editCell", { name: column.name })}
      className={box}
      value={picked}
      onChange={(event) => {
        setPicked(event.target.value);
      }}
      onKeyDown={(event) => {
        event.stopPropagation();
        const then = nextOf(event);
        if (then) {
          event.preventDefault();
          finish({ kind: "keep", value: valueOf(picked), then });
        } else if (event.key === "Escape") {
          event.preventDefault();
          finish({ kind: "cancel" });
        }
      }}
      onBlur={() => {
        finish(
          picked === initial
            ? { kind: "cancel" }
            : { kind: "keep", value: valueOf(picked), then: "stay" },
        );
      }}
    >
      <option value="">{t("matrix.empty")}</option>
      {choices.map((choice) => (
        <option key={choice.id} value={choice.id}>
          {choice.label}
        </option>
      ))}
    </select>
  );
}

/** Several choices: a list of boxes to tick. */
function ChoicesEditor({
  column,
  cell,
  onDone,
}: {
  column: ColumnView;
  cell: CellView | undefined;
  onDone: (result: EditResult) => void;
}) {
  const finish = useOnce(onDone);
  const { t } = useTranslation();
  const [chosen, setChosen] = useState<string[]>(() =>
    cell?.kept_text == null && Array.isArray(cell?.value) ? cell.value : [],
  );
  const value = (): CellValue => {
    const ordered = column.options.map((o) => o.id).filter((id) => chosen.includes(id));
    return ordered.length > 0 ? ordered : null;
  };
  return (
    <fieldset
      aria-label={t("matrix.editCell", { name: column.name })}
      className="absolute top-0 left-0 z-[var(--z-popover)] min-w-full space-y-1 rounded-xs border-2 border-primary bg-raised p-2 shadow-popover"
      onKeyDown={(event) => {
        event.stopPropagation();
        const then = nextOf(event);
        if (then) {
          event.preventDefault();
          finish({ kind: "keep", value: value(), then });
        } else if (event.key === "Escape") {
          event.preventDefault();
          finish({ kind: "cancel" });
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault();
          const boxes = [...event.currentTarget.querySelectorAll("input")];
          const at = boxes.indexOf(document.activeElement as HTMLInputElement);
          const next = boxes[at + (event.key === "ArrowDown" ? 1 : -1)];
          next?.focus();
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          finish({ kind: "keep", value: value(), then: "stay" });
        }
      }}
    >
      {column.options.map((option, index) => (
        <label key={option.id} className="flex items-center gap-2 text-ui whitespace-nowrap">
          <input
            type="checkbox"
            autoFocus={index === 0}
            checked={chosen.includes(option.id)}
            onChange={(event) => {
              const on = event.target.checked;
              setChosen((now) => (on ? [...now, option.id] : now.filter((id) => id !== option.id)));
            }}
          />
          {option.label}
        </label>
      ))}
      {column.options.length === 0 && (
        <p className="text-meta text-fg-muted">{t("matrix.noOptions")}</p>
      )}
    </fieldset>
  );
}
