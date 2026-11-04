// One chip per source: on or off before a search, and its state during and after one.
// A failed source never stops the others, so each says what happened to it alone.
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { cn } from "@/lib/cn";

import { sourceNames, type RunView, type SourceName, type SourceProgress } from "./api";

interface SourceChipsProps {
  enabled: ReadonlySet<SourceName>;
  onToggle: (source: SourceName) => void;
  live: Record<string, SourceProgress>;
  runs: RunView[];
  disabled: boolean;
}

export function SourceChips({ enabled, onToggle, live, runs, disabled }: SourceChipsProps) {
  const { t } = useTranslation();
  return (
    <div role="group" aria-label={t("search.sourcesLabel")} className="flex flex-wrap gap-2">
      {sourceNames.map((source) => (
        <button
          key={source}
          type="button"
          disabled={disabled}
          aria-pressed={enabled.has(source)}
          onClick={() => {
            onToggle(source);
          }}
          className={cn(
            "inline-flex h-7 items-center gap-2 rounded-md border px-2.5 text-ui",
            enabled.has(source)
              ? "border-primary bg-primary-soft text-fg"
              : "border-line bg-raised text-fg-muted",
          )}
        >
          {t(`search.sources.${source}`)}
          <ChipState
            live={live[source]}
            run={runs.find((candidate) => candidate.source === source)}
          />
        </button>
      ))}
    </div>
  );
}

// What a source's last update means, until its run is on record.
const liveStatus: Partial<Record<SourceProgress["state"], RunView["status"]>> = {
  done: "ok",
  partial: "partial",
  failed: "error",
};

function ChipState({ live, run }: { live: SourceProgress | undefined; run: RunView | undefined }) {
  const { t, i18n } = useTranslation();
  const count = (value: number) => value.toLocaleString(i18n.language);

  // The record says what finally happened; until then, live progress is all there is.
  if (!run && live && (live.state === "waiting" || live.state === "searching")) {
    return <span className="text-meta text-fg-muted">{t(`search.state.${live.state}`)}</span>;
  }
  if (!run && live?.state === "rate_limited") {
    // A new wait starts a new countdown.
    return <Countdown key={live.wait_seconds} seconds={live.wait_seconds ?? 0} />;
  }
  const status = run?.status ?? (live ? liveStatus[live.state] : undefined);
  const retrieved = run?.retrieved_count ?? live?.retrieved ?? 0;
  if (status === "ok") {
    return (
      <span className="text-meta text-success">
        {t("search.state.done", { count: retrieved, formatted: count(retrieved) })}
      </span>
    );
  }
  if (status === "partial") {
    return (
      <span className="text-meta text-warning">
        {t("search.state.partial", { count: retrieved, formatted: count(retrieved) })}
      </span>
    );
  }
  if (status === "error") {
    return <span className="text-meta text-danger">{t("search.state.failed")}</span>;
  }
  return null;
}

function Countdown({ seconds }: { seconds: number }) {
  const { t } = useTranslation();
  const [left, setLeft] = useState(Math.ceil(seconds));

  useEffect(() => {
    const timer = setInterval(() => {
      setLeft((current) => Math.max(0, current - 1));
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, []);

  return (
    <span className="text-meta text-warning">
      {t("search.state.rateLimited", { seconds: left })}
    </span>
  );
}

/** Why sources failed or stopped early, with what the user can do about it. */
export function SourceProblems({ runs }: { runs: RunView[] }) {
  const { t } = useTranslation();
  const problems = runs.filter((run) => run.error);
  if (problems.length === 0) return null;
  return (
    <ul className="space-y-1 text-meta">
      {problems.map((run) => {
        const code = run.error?.code ?? "unknown";
        return (
          <li
            key={run.source}
            className={run.status === "partial" ? "text-warning" : "text-danger"}
          >
            <span className="font-medium">{t(`search.sources.${run.source}`, run.source)}: </span>
            {t(`errors.${code}`, { ...run.error?.params, defaultValue: t("errors.unknown") })}
            {code === "source.key_required" && (
              <>
                {" "}
                <Link to="/settings/sources" className="underline">
                  {t("search.addKey")}
                </Link>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
