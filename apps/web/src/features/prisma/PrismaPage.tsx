// The PRISMA 2020 flow diagram (design 5.7, Task 35): numbers from Task 34, box titles the
// user may rewrite (kept per review), a colour and a black-and-white print theme, and SVG or
// PNG export of exactly what is on screen.
import type { TFunction } from "i18next";
import { Download, Pencil, Printer } from "lucide-react";
import { useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useActiveReview } from "@/features/reviews/store";
import { ApiError } from "@/lib/api/query";
import { saveBlob } from "@/lib/download";

import { usePrismaCounts, usePrismaLabels, useSaveLabels } from "./api";
import {
  boxKeys,
  prismaSvg,
  printPalette,
  type BoxKey,
  type DiagramText,
  type Palette,
  type PrismaCounts,
} from "./diagram";

type Theme = "color" | "print";

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  return t(`errors.${code}`, { defaultValue: t("errors.unknown") });
}

/** The screen's own colours, resolved, so the exported file needs no stylesheet. */
function themePalette(): Palette {
  const style = getComputedStyle(document.documentElement);
  const value = (name: string) => style.getPropertyValue(name).trim();
  return {
    text: value("--color-text-primary"),
    muted: value("--color-text-muted"),
    line: value("--color-border-strong"),
    fill: value("--color-bg-raised"),
    page: value("--color-bg-canvas"),
    database: value("--color-accent-default"),
    other: value("--color-status-ai"),
    excluded: value("--color-status-excluded"),
  };
}

export function useDiagramText(labels: Partial<Record<BoxKey, string>>): DiagramText {
  const { t, i18n } = useTranslation();
  return useMemo(() => {
    const number = new Intl.NumberFormat(i18n.language);
    return {
      title: (key) => labels[key] ?? t(`prisma.boxes.${key}`),
      n: (value) => t("prisma.n", { n: number.format(value) }),
      line: (label, value) => t("prisma.line", { label, n: number.format(value) }),
      source: (name) => (name ? t(`search.sources.${name}`, name) : t("prisma.unlogged")),
      method: (method, round) =>
        round === null ? t(`prisma.methods.${method}`) : t(`prisma.methods.${method}`, { round }),
      reason: (code, text) => (code ? `${code}: ${text ?? ""}` : t("prisma.noReason")),
      awaiting: t("prisma.awaiting"),
      duplicates: t("prisma.duplicates"),
      notTaken: t("prisma.notTaken"),
      documentTitle: t("prisma.documentTitle"),
    };
  }, [labels, t, i18n.language]);
}

async function toPng(svg: string): Promise<Blob> {
  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  await image.decode();
  // Twice the size, so the picture stays sharp in a document.
  const canvas = document.createElement("canvas");
  canvas.width = image.width * 2;
  canvas.height = image.height * 2;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("no 2d canvas");
  context.scale(2, 2);
  context.drawImage(image, 0, 0);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("the PNG could not be made"));
    }, "image/png");
  });
}

export function PrismaPage() {
  const { t } = useTranslation();
  const review = useActiveReview();
  if (!review) {
    return (
      <div className="p-6 text-ui">
        <h1 className="text-h2">{t("prisma.title")}</h1>
        <p className="mt-2 text-fg-muted">{t("prisma.noReview")}</p>
      </div>
    );
  }
  return <Diagram key={review.id} reviewId={review.id} reviewTitle={review.title} />;
}

function Diagram({ reviewId, reviewTitle }: { reviewId: string; reviewTitle: string }) {
  const { t } = useTranslation();
  const counts = usePrismaCounts(reviewId);
  const labels = usePrismaLabels(reviewId);
  const [theme, setTheme] = useState<Theme>("color");
  const [editing, setEditing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const text = useDiagramText(labels.data ?? {});
  const svg = useMemo(
    () =>
      counts.data
        ? prismaSvg(counts.data, text, theme === "print" ? printPalette : themePalette())
        : null,
    [counts.data, text, theme],
  );
  const fileName = `prisma-${reviewTitle.replace(/[^\p{L}\p{N}]+/gu, "-").toLowerCase()}`;

  return (
    <div className="space-y-4 p-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="min-w-0 flex-1 text-h2">{t("prisma.title")}</h1>
        <Segmented
          aria-label={t("prisma.theme.label")}
          value={theme}
          onValueChange={setTheme}
          options={[
            { value: "color", label: t("prisma.theme.color") },
            { value: "print", label: t("prisma.theme.print") },
          ]}
        />
        <Button
          variant={editing ? "secondary" : "ghost"}
          aria-pressed={editing}
          onClick={() => {
            setEditing(!editing);
          }}
        >
          <Pencil aria-hidden />
          {t("prisma.editLabels")}
        </Button>
        <Button
          disabled={!svg}
          onClick={() => {
            if (svg) saveBlob(`${fileName}.svg`, new Blob([svg], { type: "image/svg+xml" }));
          }}
        >
          <Download aria-hidden />
          {t("prisma.exportSvg")}
        </Button>
        <Button
          disabled={!svg}
          onClick={() => {
            if (!svg) return;
            setProblem(null);
            toPng(svg)
              .then((png) => {
                saveBlob(`${fileName}.png`, png);
              })
              .catch((error: unknown) => {
                setProblem(errorText(t, error));
              });
          }}
        >
          <Printer aria-hidden />
          {t("prisma.exportPng")}
        </Button>
      </header>
      <p className="text-meta text-fg-muted">
        {t("prisma.hint")}{" "}
        <Link to="/review" className="text-primary underline">
          {t("prisma.back")}
        </Link>
      </p>
      {problem && (
        <p role="alert" className="text-meta text-danger">
          {problem}
        </p>
      )}
      {counts.isError && (
        <p role="alert" className="text-ui text-danger">
          {errorText(t, counts.error)}
        </p>
      )}
      {editing && (
        <LabelEditor
          reviewId={reviewId}
          saved={labels.data ?? {}}
          onDone={() => {
            setEditing(false);
          }}
        />
      )}
      {svg && (
        <figure
          aria-label={t("prisma.documentTitle")}
          className="overflow-auto rounded-md border border-line bg-raised p-2"
          // The SVG is built here from numbers and escaped text (diagram.ts), never from HTML.
          dangerouslySetInnerHTML={{ __html: svg.replace(/^<\?xml[^>]*>\s*/, "") }}
        />
      )}
    </div>
  );
}

function LabelEditor({
  reviewId,
  saved,
  onDone,
}: {
  reviewId: string;
  saved: Partial<Record<BoxKey, string>>;
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const save = useSaveLabels(reviewId);
  const [draft, setDraft] = useState<Partial<Record<BoxKey, string>>>(saved);

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    const labels = Object.fromEntries(
      Object.entries(draft)
        .map(([key, value]) => [key, value.trim()] as const)
        .filter(([, value]) => value !== ""),
    );
    save.mutate(labels, { onSuccess: onDone });
  }

  return (
    <form
      aria-label={t("prisma.editLabels")}
      onSubmit={submit}
      className="grid gap-2 rounded-md border border-line bg-raised p-3 md:grid-cols-2"
    >
      <p className="text-meta text-fg-muted md:col-span-2">{t("prisma.labelsHint")}</p>
      {boxKeys.map((key) => (
        <label key={key} className="flex flex-col gap-1 text-meta text-fg-muted">
          {t(`prisma.boxes.${key}`)}
          <Input
            placeholder={t(`prisma.boxes.${key}`)}
            maxLength={200}
            value={draft[key] ?? ""}
            onChange={(event) => {
              setDraft({ ...draft, [key]: event.target.value });
            }}
          />
        </label>
      ))}
      <div className="flex gap-2 md:col-span-2">
        <Button type="submit" variant="primary" disabled={save.isPending}>
          {t("prisma.saveLabels")}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t("prisma.cancel")}
        </Button>
        {save.isError && (
          <p role="alert" className="text-meta text-danger">
            {errorText(t, save.error)}
          </p>
        )}
      </div>
    </form>
  );
}

/** The review panel's small summary (Task 35): the same counts, in one line per stage. */
export function PrismaSummary({ counts }: { counts: PrismaCounts }) {
  const { t, i18n } = useTranslation();
  const number = new Intl.NumberFormat(i18n.language);
  const both = (pick: (branch: Omit<PrismaCounts["databases"], "sources">) => number) =>
    number.format(pick(counts.databases) + pick(counts.other_methods));
  const rows: [string, string][] = [
    [t("prisma.summary.identified"), both((b) => b.identified)],
    [t("prisma.summary.duplicates"), both((b) => b.duplicates)],
    [t("prisma.summary.screened"), both((b) => b.screened)],
    [t("prisma.summary.notRetrieved"), both((b) => b.not_retrieved)],
    [t("prisma.summary.assessed"), both((b) => b.assessed)],
    [t("prisma.summary.included"), number.format(counts.included)],
  ];
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-ui">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-fg-muted">{label}</dt>
          <dd className="text-right tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
