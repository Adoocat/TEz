// The criteria panel (design 5.2, right): each criterion with its 1-9 key. Clicking one
// decides with it: an exclusion criterion excludes for that reason, an inclusion one includes.
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { cn } from "@/lib/cn";

import type { StageCriterion } from "./api";

export function CriteriaSidebar({
  criteria,
  chosenId,
  disabled,
  onChoose,
}: {
  criteria: readonly StageCriterion[];
  chosenId: string | null | undefined;
  disabled: boolean;
  onChoose: (criterion: StageCriterion) => void;
}) {
  const { t } = useTranslation();
  const groups = [
    { kind: "inclusion" as const, items: criteria.filter((c) => c.kind === "inclusion") },
    { kind: "exclusion" as const, items: criteria.filter((c) => c.kind === "exclusion") },
  ];

  return (
    <aside
      aria-label={t("screening.criteria.title")}
      className="w-inspector shrink-0 space-y-4 overflow-y-auto border-l border-line bg-surface p-4"
    >
      <h2 className="text-h3">{t("screening.criteria.title")}</h2>
      {criteria.length === 0 && (
        <p className="text-meta text-fg-muted">
          {t("screening.criteria.none")}{" "}
          <Link to="/review" className="text-primary underline">
            {t("screening.criteria.edit")}
          </Link>
        </p>
      )}
      {groups.map(
        ({ kind, items }) =>
          items.length > 0 && (
            <section key={kind} aria-labelledby={`screening-criteria-${kind}`}>
              <h3
                id={`screening-criteria-${kind}`}
                className={cn(
                  "mb-1 text-meta font-semibold",
                  kind === "inclusion" ? "text-success" : "text-danger",
                )}
              >
                {t(`screening.criteria.${kind}`)}
              </h3>
              <ul className="space-y-1">
                {items.map((criterion) => (
                  <li key={criterion.id}>
                    <button
                      type="button"
                      disabled={disabled}
                      aria-pressed={chosenId === criterion.id}
                      aria-keyshortcuts={
                        criterion.shortcut ? String(criterion.shortcut) : undefined
                      }
                      aria-label={t(`screening.criteria.choose.${kind}`, {
                        code: criterion.code,
                        text: criterion.text,
                      })}
                      onClick={() => {
                        onChoose(criterion);
                      }}
                      className={cn(
                        "flex w-full items-start gap-2 rounded-md border border-line bg-raised p-2 text-left text-ui hover:bg-hovered disabled:opacity-60",
                        chosenId === criterion.id && "border-primary bg-primary-soft",
                      )}
                    >
                      {criterion.shortcut !== null ? (
                        <kbd className="rounded-xs border border-kbd-line bg-kbd px-1.5 font-mono text-meta">
                          {criterion.shortcut}
                        </kbd>
                      ) : (
                        <span className="w-5" />
                      )}
                      <span
                        className={cn(
                          "font-mono text-meta",
                          kind === "inclusion" ? "text-success" : "text-danger",
                        )}
                      >
                        {criterion.code}
                      </span>
                      <span className="min-w-0 flex-1">{criterion.text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ),
      )}
    </aside>
  );
}
