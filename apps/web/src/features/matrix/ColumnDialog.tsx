// Adding or editing a matrix column (Task 52): name, what to write there, type and choices.
// A new type or new choices are tried first; if some cells cannot be converted, the dialog
// names them and asks before changing (ADR 0035: they are kept as text, never dropped).
import { Plus, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";

import {
  useAddColumn,
  useChangeType,
  useUpdateColumn,
  type ColumnView,
  type DataType,
  type RowView,
  type TypeChangeReport,
} from "./api";
import { TYPE_ICONS } from "./MatrixGrid";
import { CHOICE_TYPES } from "./values";

const TYPES: DataType[] = ["text", "number", "enum", "multi_enum", "bool"];
// How many kept cells the warning names; the count covers them all.
const NAMED = 5;

interface DraftOption {
  id: string | null;
  label: string;
}

export function ColumnDialog({
  matrixId,
  column,
  rows,
  onClose,
}: {
  matrixId: string;
  /** Null adds a column. */
  column: ColumnView | null;
  rows: RowView[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const add = useAddColumn(matrixId);
  const update = useUpdateColumn(matrixId);
  const change = useChangeType(matrixId);
  const [name, setName] = useState(column?.name ?? "");
  const [instruction, setInstruction] = useState(column?.instruction ?? "");
  const [type, setType] = useState<DataType>(column?.data_type ?? "text");
  const [options, setOptions] = useState<DraftOption[]>(
    () => column?.options.map((o) => ({ id: o.id, label: o.label })) ?? [],
  );
  const [warning, setWarning] = useState<TypeChangeReport | null>(null);
  const pending = add.isPending || update.isPending || change.isPending;
  const error = add.error ?? update.error ?? change.error;
  const choices = CHOICE_TYPES.includes(type);
  const cleanOptions = options
    .map((o) => ({ id: o.id, label: o.label.trim() }))
    .filter((o) => o.label !== "");

  const optionsChanged =
    column !== null &&
    choices &&
    JSON.stringify(cleanOptions) !==
      JSON.stringify(column.options.map((o) => ({ id: o.id, label: o.label })));
  const typeChanged = column !== null && (type !== column.data_type || optionsChanged);

  const typeChange = (dryRun: boolean) => ({
    data_type: type,
    // Left out when switching to choices from a free type: the cells' own words become them.
    options:
      choices && (cleanOptions.length > 0 || CHOICE_TYPES.includes(column?.data_type ?? "text"))
        ? cleanOptions
        : null,
    dry_run: dryRun,
    true_text: t("matrix.yes"),
    false_text: t("matrix.no"),
  });

  async function save(confirmed: boolean) {
    if (column === null) {
      await add.mutateAsync({
        name: name.trim(),
        instruction: instruction.trim() || null,
        data_type: type,
        options: choices ? cleanOptions : [],
      });
      onClose();
      return;
    }
    if (name.trim() !== column.name || instruction.trim() !== (column.instruction ?? "")) {
      await update.mutateAsync({
        id: column.id,
        patch: { name: name.trim(), instruction: instruction.trim() },
      });
    }
    if (typeChanged) {
      if (!confirmed) {
        const report = await change.mutateAsync({ id: column.id, change: typeChange(true) });
        if (report.kept.length > 0) {
          setWarning(report);
          return;
        }
      }
      await change.mutateAsync({ id: column.id, change: typeChange(false) });
    }
    onClose();
  }

  const titles = new Map(rows.map((row) => [row.paper_id, row.title]));

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[12%] left-1/2 z-[var(--z-dialog)] max-h-[80vh] w-112 max-w-[92vw] -translate-x-1/2 space-y-3 overflow-y-auto rounded-lg border border-line bg-raised p-4 shadow-popover"
        >
          <Dialog.Title className="text-h3">
            {column ? t("matrix.editColumn") : t("matrix.addColumn")}
          </Dialog.Title>
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void save(warning !== null).catch(() => undefined);
            }}
          >
            <label className="block space-y-1">
              <span className="text-meta text-fg-muted">{t("matrix.columnName")}</span>
              <Input
                required
                autoFocus
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-meta text-fg-muted">{t("matrix.instruction")}</span>
              <textarea
                rows={2}
                className="w-full rounded-md border border-line bg-raised px-2 py-1.5 text-ui"
                placeholder={t("matrix.instructionHint")}
                value={instruction}
                onChange={(event) => {
                  setInstruction(event.target.value);
                }}
              />
            </label>
            <fieldset className="space-y-1">
              <legend className="text-meta text-fg-muted">{t("matrix.type")}</legend>
              <div className="flex flex-wrap gap-1">
                {TYPES.map((option) => {
                  const Icon = TYPE_ICONS[option];
                  return (
                    <label
                      key={option}
                      className="flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 text-ui has-checked:border-primary has-checked:bg-hovered"
                    >
                      <input
                        type="radio"
                        name="data-type"
                        className="sr-only"
                        checked={type === option}
                        onChange={() => {
                          setType(option);
                          setWarning(null);
                        }}
                      />
                      <Icon aria-hidden className="size-3.5" />
                      {t(`matrix.types.${option}`)}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            {choices && (
              <fieldset className="space-y-1">
                <legend className="text-meta text-fg-muted">{t("matrix.options")}</legend>
                {options.map((option, index) => (
                  <div key={option.id ?? `new-${String(index)}`} className="flex gap-1">
                    <Input
                      aria-label={t("matrix.optionN", { n: index + 1 })}
                      value={option.label}
                      onChange={(event) => {
                        const label = event.target.value;
                        setOptions((now) => now.map((o, i) => (i === index ? { ...o, label } : o)));
                        setWarning(null);
                      }}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      aria-label={t("matrix.removeOption", { label: option.label })}
                      onClick={() => {
                        setOptions((now) => now.filter((_, i) => i !== index));
                        setWarning(null);
                      }}
                    >
                      <X aria-hidden />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setOptions((now) => [...now, { id: null, label: "" }]);
                  }}
                >
                  <Plus aria-hidden />
                  {t("matrix.addOption")}
                </Button>
                {column && !CHOICE_TYPES.includes(column.data_type) && options.length === 0 && (
                  <p className="text-meta text-fg-muted">{t("matrix.optionsFromCells")}</p>
                )}
              </fieldset>
            )}
            {warning && (
              <div role="alert" className="space-y-1 rounded-md border border-warning p-2 text-ui">
                <p>
                  {t("matrix.keptWarning", { count: warning.kept.length, cells: warning.cells })}
                </p>
                <ul className="list-disc pl-5 text-meta text-fg-muted">
                  {warning.kept.slice(0, NAMED).map((kept) => (
                    <li key={kept.paper_id}>
                      {titles.get(kept.paper_id) ?? kept.paper_id}: “{kept.text}”
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {error && (
              <p role="alert" className="text-meta text-danger">
                {t(`errors.${error instanceof ApiError ? error.code : "unknown"}`, {
                  defaultValue: t("errors.unknown"),
                })}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" onClick={onClose}>
                {t("matrix.cancel")}
              </Button>
              <Button type="submit" variant="primary" disabled={pending || name.trim() === ""}>
                {warning
                  ? t("matrix.changeAnyway")
                  : column
                    ? t("matrix.save")
                    : t("matrix.addColumn")}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
