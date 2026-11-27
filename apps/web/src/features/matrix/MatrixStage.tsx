// The data extraction stage on the review panel (design 5.1, Task 54): how full the review's
// matrices are and how much rests on passages, with the way in.
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";

import { useMatrices } from "./api";

export function MatrixStageCard({ reviewId }: { reviewId: string }) {
  const { t, i18n } = useTranslation();
  const matrices = useMatrices(reviewId);
  if (!matrices.data) return null;
  const number = (value: number) => value.toLocaleString(i18n.language);
  const name = t("matrix.stage.name");
  const cells = matrices.data.reduce((sum, m) => sum + m.rows * m.columns, 0);
  const filled = matrices.data.reduce((sum, m) => sum + m.coverage.filled, 0);
  const sourced = matrices.data.reduce((sum, m) => sum + m.coverage.sourced, 0);
  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <h3 className="text-ui font-medium">{name}</h3>
      {matrices.data.length === 0 ? (
        <p className="text-meta text-fg-muted">{t("matrix.stage.none")}</p>
      ) : (
        <>
          <p className="text-meta text-fg-muted">
            {t("matrix.stage.filled", { filled: number(filled), cells: number(cells) })}
          </p>
          <div
            role="progressbar"
            aria-label={name}
            aria-valuemin={0}
            aria-valuemax={cells}
            aria-valuenow={filled}
            className="h-1 overflow-hidden rounded-full bg-line"
          >
            <div
              className="h-full bg-primary"
              style={{ width: `${String(cells === 0 ? 0 : (filled / cells) * 100)}%` }}
            />
          </div>
          {filled > 0 && (
            <p className="text-meta text-fg-muted">
              {t("matrix.stage.sourced", { percent: Math.round((100 * sourced) / filled) })}
            </p>
          )}
        </>
      )}
      <Button
        asChild
        size="sm"
        variant="secondary"
        aria-label={t("reviews.panel.continueStage", { stage: name })}
      >
        <Link to="/matrix">
          {t("reviews.panel.continue")}
          <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}
