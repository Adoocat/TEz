// The reader's Matrix tab (design 4.5, Task 53): the cells of the paper being read, in each
// matrix it is a row of, with how many passages back each, and a way to that cell.
import { Link2, Table2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useAttachment } from "@/features/files/api";

import { usePaperMatrices } from "./api";
import { matrixCellPath } from "./store";
import { cellText } from "./values";

export function PaperCells({ attachmentId }: { attachmentId: string }) {
  const { t, i18n } = useTranslation();
  const paperId = useAttachment(attachmentId).data?.paper_id ?? null;
  const matrices = usePaperMatrices(paperId);
  if (!matrices.data) return null;
  if (matrices.data.length === 0) {
    return <p className="text-meta text-fg-muted">{t("matrix.reader.none")}</p>;
  }
  return (
    <div className="space-y-4">
      {matrices.data.map((matrix) => (
        <section key={matrix.matrix_id} aria-label={matrix.matrix_name} className="space-y-2">
          <h2 className="flex items-center gap-1.5 text-h3">
            <Table2 aria-hidden className="size-4 text-fg-muted" />
            {matrix.matrix_name}
          </h2>
          {matrix.columns.length === 0 && (
            <p className="text-meta text-fg-muted">{t("matrix.noColumns")}</p>
          )}
          <ul className="space-y-1">
            {matrix.columns.map((column) => {
              const cell = matrix.cells.find((c) => c.column_id === column.id);
              const text = cellText(column, cell, t, i18n.language);
              const sources = cell?.evidence.length ?? 0;
              return (
                <li key={column.id}>
                  <Link
                    to={matrixCellPath({
                      matrixId: matrix.matrix_id,
                      paperId: paperId ?? "",
                      columnId: column.id,
                    })}
                    aria-label={t("matrix.reader.openCell", { name: column.name })}
                    className="block rounded-md border border-line px-2 py-1.5 hover:bg-hovered"
                  >
                    <span className="flex items-center gap-1 text-meta text-fg-muted">
                      {column.name}
                      {sources > 0 && (
                        <span className="ml-auto flex items-center gap-0.5 text-primary">
                          <Link2 aria-hidden className="size-3" />
                          {t("matrix.evidence.sources", { count: sources })}
                        </span>
                      )}
                    </span>
                    <span className="line-clamp-2 text-ui">
                      {text || <span className="text-fg-muted">{t("matrix.empty")}</span>}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
