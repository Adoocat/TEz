// The reading panel's Structure tab (Task 56): the paper's sections, each taking the reader
// to its page, and its reference list, those in the library marked. Read by GROBID on request.
import { BookMarked, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/query";

import { stampOf, useReadStructure, useStructure } from "./api";

export function PaperStructure({ attachmentId }: { attachmentId: string }) {
  const { t } = useTranslation();
  const [asked, setAsked] = useState<string | null>(null);
  const structure = useStructure(attachmentId, asked);
  const read = useReadStructure(attachmentId);
  const data = structure.data;
  // Waiting until the reading is newer than when it was asked for, or has failed.
  const stamp = stampOf(data);
  const waiting = asked !== null && stamp === asked;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={waiting || read.isPending}
          onClick={() => {
            read.mutate(undefined, {
              onSuccess: () => {
                setAsked(stamp);
              },
            });
          }}
        >
          <RefreshCw aria-hidden className={waiting ? "animate-spin" : undefined} />
          {data.read_at ? t("structure.readAgain") : t("structure.read")}
        </Button>
        {waiting && <span className="text-meta text-fg-muted">{t("structure.reading")}</span>}
      </div>
      {!data.read_at && !waiting && !data.error && (
        <p className="text-meta text-fg-muted">{t("structure.notRead")}</p>
      )}
      {data.error && !waiting && (
        <p role="alert" className="text-meta text-danger">
          {t(`errors.${data.error}`, { defaultValue: t("errors.unknown") })}
        </p>
      )}
      {read.error && (
        <p role="alert" className="text-meta text-danger">
          {t(`errors.${read.error instanceof ApiError ? read.error.code : "unknown"}`, {
            defaultValue: t("errors.unknown"),
          })}
        </p>
      )}
      {data.sections.length > 0 && (
        <section aria-labelledby="structure-sections" className="space-y-1">
          <h2 id="structure-sections" className="text-h3">
            {t("structure.sections")}
          </h2>
          <ul className="space-y-0.5">
            {data.sections.map((section, index) => (
              <li key={`${section.heading}-${String(index)}`}>
                {section.page_start ? (
                  <Link
                    to={`/reader/${attachmentId}?page=${String(section.page_start)}`}
                    className="flex items-baseline gap-2 rounded-xs px-1 py-0.5 text-ui hover:bg-hovered"
                  >
                    <span className="min-w-0 flex-1 truncate">{section.heading}</span>
                    <span className="shrink-0 text-meta text-fg-muted">
                      {t(`structure.types.${section.type}`, { defaultValue: "" })}
                      {" · "}
                      {t("structure.page", { page: section.page_start })}
                    </span>
                  </Link>
                ) : (
                  <span className="block truncate px-1 py-0.5 text-ui text-fg-muted">
                    {section.heading}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.references.length > 0 && (
        <section aria-labelledby="structure-references" className="space-y-1">
          <h2 id="structure-references" className="text-h3">
            {t("structure.references", { count: data.references.length })}
          </h2>
          <ol className="list-decimal space-y-1.5 pl-5">
            {data.references.map((reference) => (
              <li key={reference.ord} className="text-meta">
                <span>{reference.raw_text}</span>
                {reference.matched_paper_id && (
                  <span className="ml-1 inline-flex items-center gap-0.5 text-primary">
                    <BookMarked aria-hidden className="size-3" />
                    {t("structure.inLibrary")}
                  </span>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
