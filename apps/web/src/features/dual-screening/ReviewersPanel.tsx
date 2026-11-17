// The review panel's two-reviewer section (Task 41): everyone screens in their own library and
// shares decisions as a file. Export mine under my name; import a colleague's file and see what
// matched.
import { Download, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import { useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";

import { useExportDecisions, useImportDecisions, useReviewers, type ImportReport } from "./api";

/** The name this person exports under, kept on this device. */
export const useReviewerName = create<{ name: string; setName: (name: string) => void }>()(
  persist(
    (set) => ({
      name: "",
      setName: (name) => {
        set({ name });
      },
    }),
    { name: "tez.reviewer-name" },
  ),
);

function fileSlug(name: string): string {
  return (
    name
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-|-$/g, "")
      .toLowerCase() || "reviewer"
  );
}

export function ReviewersPanel({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const { platform } = useBackend();
  const { name, setName } = useReviewerName();
  const reviewers = useReviewers(reviewId);
  const exporting = useExportDecisions(reviewId);
  const importing = useImportDecisions(reviewId);
  const picker = useRef<HTMLInputElement>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const failure = exporting.error ?? importing.error;

  const others = (reviewers.data ?? []).filter((r) => r !== "owner" && r !== "consensus");

  return (
    <section aria-labelledby="review-reviewers" className="space-y-3">
      <h2 id="review-reviewers" className="text-h3">
        {t("dual.title")}
      </h2>
      <p className="text-meta text-fg-muted">{t("dual.hint")}</p>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-56 flex-col gap-1 text-meta text-fg-muted">
          {t("dual.name")}
          <Input
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </label>
        <Button
          disabled={!name.trim() || exporting.isPending}
          onClick={() => {
            setNotice(null);
            exporting.mutate(name.trim(), {
              onSuccess: (file) => {
                const fileName = `decisions-${fileSlug(name)}.json`;
                void platform
                  .saveFile(fileName, `${JSON.stringify(file, null, 2)}\n`, "application/json")
                  .then(() => {
                    setNotice(t("dual.exported", { fileName, count: file.decisions?.length ?? 0 }));
                  });
              },
            });
          }}
        >
          <Download aria-hidden />
          {t("dual.export")}
        </Button>
        <Button
          disabled={importing.isPending}
          onClick={() => {
            picker.current?.click();
          }}
        >
          <Upload aria-hidden />
          {t("dual.import")}
        </Button>
        <input
          ref={picker}
          type="file"
          accept=".json,application/json"
          className="hidden"
          data-testid="decision-file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (!file) return;
            setNotice(null);
            void file.text().then((content) => {
              importing.mutate(content);
            });
          }}
        />
      </div>
      <p className="text-meta text-fg-muted">
        {others.length === 0
          ? t("dual.noColleagues")
          : t("dual.colleagues", { names: others.join(", ") })}
      </p>
      {notice && (
        <p role="status" className="text-meta text-fg-muted">
          {notice}
        </p>
      )}
      {failure && (
        <p role="alert" className="text-meta text-danger">
          {t(`errors.${failure instanceof ApiError ? failure.code : "unknown"}`, {
            defaultValue: t("errors.unknown"),
          })}
        </p>
      )}
      {importing.data && <Report report={importing.data} />}
    </section>
  );
}

function Report({ report }: { report: ImportReport }) {
  const { t } = useTranslation();
  return (
    <div role="status" className="space-y-2 rounded-md border border-line bg-raised p-3 text-ui">
      <p>
        {t("dual.report.summary", {
          reviewer: report.reviewer,
          matched: report.matched,
          records: report.records,
        })}
      </p>
      <p className="text-meta text-fg-muted">
        {t("dual.report.counts", {
          added: report.added,
          corrected: report.corrected,
          unchanged: report.unchanged,
        })}
        {report.withdrawn > 0 && ` ${t("dual.report.withdrawn", { count: report.withdrawn })}`}
      </p>
      {report.unmatched.length > 0 && (
        <div>
          <p className="text-meta">
            {t("dual.report.unmatched", { count: report.unmatched.length })}
          </p>
          <ul className="list-disc pl-5 text-meta text-fg-muted">
            {report.unmatched.map((record) => (
              <li key={record.ref}>
                {record.title} — {t(`dual.problem.${record.problem}`)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {report.unknown_criteria.length > 0 && (
        <p className="text-meta text-danger">
          {t("dual.report.unknownCriteria", {
            codes: report.unknown_criteria
              .map((c) => `${c.code} (${String(c.decisions)})`)
              .join(", "),
          })}
        </p>
      )}
      {report.skipped.length > 0 && (
        <p className="text-meta text-danger">
          {t("dual.report.skipped", { count: report.skipped.length })}
        </p>
      )}
    </div>
  );
}
