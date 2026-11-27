// "Link to a matrix cell" from the reader (design 5.4, Task 53): which cell of this paper's row
// the selected passage backs. An empty text cell can take the passage as its value.
import { Link2 } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import type { AnchorView } from "@/features/reader/api";
import { ApiError } from "@/lib/api/query";

import { useLinkEvidence, usePaperMatrices } from "./api";
import type { ActiveCell } from "./store";
import { cellText } from "./values";

export interface LinkedCell extends ActiveCell {
  columnName: string;
}

export function LinkToCell({
  anchor,
  onDone,
  onCancel,
}: {
  anchor: AnchorView;
  onDone: (cell: LinkedCell) => void;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const paperId = anchor.paper.id;
  const matrices = usePaperMatrices(paperId);
  const link = useLinkEvidence();
  const [fill, setFill] = useState(true);

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[15%] left-1/2 z-[var(--z-dialog)] max-h-[75vh] w-112 max-w-[90vw] -translate-x-1/2 space-y-3 overflow-y-auto rounded-lg border border-line bg-raised p-4 shadow-popover"
        >
          <Dialog.Title className="text-h3">{t("matrix.link.title")}</Dialog.Title>
          <blockquote className="line-clamp-3 border-l-2 border-line-strong pl-2 font-serif text-ui text-fg-muted italic">
            {anchor.quote}
          </blockquote>
          {matrices.data?.length === 0 && (
            <p className="text-meta text-fg-muted">{t("matrix.reader.none")}</p>
          )}
          {matrices.data?.map((matrix) => (
            <section key={matrix.matrix_id} aria-label={matrix.matrix_name} className="space-y-1">
              {matrices.data.length > 1 && (
                <h3 className="text-meta font-medium text-fg-muted">{matrix.matrix_name}</h3>
              )}
              <ul className="space-y-1">
                {matrix.columns.map((column) => {
                  const cell = matrix.cells.find((c) => c.column_id === column.id);
                  const text = cellText(column, cell, t, i18n.language);
                  return (
                    <li key={column.id}>
                      <Button
                        variant="ghost"
                        className="h-auto w-full justify-start py-1.5 text-left"
                        disabled={link.isPending}
                        onClick={() => {
                          const target = {
                            matrixId: matrix.matrix_id,
                            paperId,
                            columnId: column.id,
                          };
                          link.mutate(
                            { ...target, anchorId: anchor.id, fill },
                            {
                              onSuccess: () => {
                                onDone({ ...target, columnName: column.name });
                              },
                            },
                          );
                        }}
                      >
                        <Link2 aria-hidden />
                        <span className="min-w-0">
                          <span className="block truncate">{column.name}</span>
                          {text && (
                            <span className="block truncate text-meta text-fg-muted">{text}</span>
                          )}
                        </span>
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
          <label className="flex items-center gap-2 text-ui">
            <input
              type="checkbox"
              checked={fill}
              onChange={(event) => {
                setFill(event.target.checked);
              }}
            />
            {t("matrix.link.fill")}
          </label>
          {link.error && (
            <p role="alert" className="text-meta text-danger">
              {t(`errors.${link.error instanceof ApiError ? link.error.code : "unknown"}`, {
                defaultValue: t("errors.unknown"),
              })}
            </p>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
