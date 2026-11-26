// The panel beside the matrix (design 5.4): the active cell, its value and the passages it
// rests on, each with its page and a way into the PDF (Task 53).
import { ExternalLink, MapPinOff, Unlink } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/query";

import { useMatrix, useUnlinkEvidence } from "./api";
import { useMatrixSelection } from "./store";
import { cellText } from "./values";

export function MatrixInspector() {
  const { t, i18n } = useTranslation();
  const active = useMatrixSelection((state) => state.cell);
  const matrix = useMatrix(active?.matrixId ?? null);
  const unlink = useUnlinkEvidence();
  const row = matrix.data?.rows.find((r) => r.paper_id === active?.paperId);
  const column = matrix.data?.columns.find((c) => c.id === active?.columnId);
  if (!active || !row || !column) {
    return (
      <div className="space-y-2">
        <h2 className="text-h3">{t("matrix.evidence.title")}</h2>
        <p className="text-meta text-fg-muted">{t("matrix.evidence.pickCell")}</p>
      </div>
    );
  }
  const cell = row.cells.find((c) => c.column_id === column.id);
  const value = cellText(column, cell, t, i18n.language);
  const evidence = cell?.evidence ?? [];

  return (
    <section aria-label={t("matrix.evidence.title")} className="space-y-4">
      <header className="space-y-0.5">
        <h2 className="text-h3">{column.name}</h2>
        <p className="line-clamp-2 text-meta text-fg-muted">{row.title}</p>
      </header>
      <div className="space-y-1">
        <h3 className="text-meta font-medium text-fg-muted uppercase">
          {t("matrix.evidence.value")}
        </h3>
        <p className="rounded-md border border-line bg-surface px-3 py-2 text-ui">
          {value || <span className="text-fg-muted">{t("matrix.empty")}</span>}
        </p>
        {cell?.kept_text != null && <p className="text-meta text-warning">{t("matrix.kept")}</p>}
      </div>
      <div className="space-y-2">
        <h3 className="text-meta font-medium text-fg-muted uppercase">
          {t("matrix.evidence.passages", { count: evidence.length })}
        </h3>
        {evidence.length === 0 && (
          <p className="text-meta text-fg-muted">{t("matrix.evidence.none")}</p>
        )}
        <ul className="space-y-2">
          {evidence.map((item) => (
            <li key={item.anchor_id} className="space-y-1.5 rounded-md border border-line p-2">
              <blockquote className="border-l-2 border-line-strong pl-2 font-serif text-ui italic">
                “{item.quote}”
              </blockquote>
              <div className="flex items-center gap-2 text-meta">
                <span className="rounded-xs bg-surface px-1.5 py-0.5 font-mono">
                  {t("matrix.evidence.page", { page: item.page })}
                </span>
                {item.status === "lost" && (
                  <span className="flex items-center gap-1 text-warning">
                    <MapPinOff aria-hidden className="size-3.5" />
                    {t("matrix.evidence.lost")}
                  </span>
                )}
                <Link
                  to={`/reader/${item.attachment_id}?anchor=${item.anchor_id}`}
                  className="ml-auto flex items-center gap-1 text-primary hover:underline"
                >
                  <ExternalLink aria-hidden className="size-3.5" />
                  {t("matrix.evidence.open")}
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={t("matrix.evidence.unlink")}
                  disabled={unlink.isPending}
                  onClick={() => {
                    unlink.mutate({ ...active, anchorId: item.anchor_id });
                  }}
                >
                  <Unlink aria-hidden />
                </Button>
              </div>
            </li>
          ))}
        </ul>
        {unlink.error && (
          <p role="alert" className="text-meta text-danger">
            {t(`errors.${unlink.error instanceof ApiError ? unlink.error.code : "unknown"}`, {
              defaultValue: t("errors.unknown"),
            })}
          </p>
        )}
        <p className="text-meta text-fg-muted">{t("matrix.evidence.how")}</p>
      </div>
    </section>
  );
}
