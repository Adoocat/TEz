// Grey literature on the review panel (Task 37): add a thesis, report, register record or
// web page by hand. It is matched against the library like any record, counted in its PRISMA
// other-methods box and goes to screening. Imports from websites or organisations are
// marked in the import dialog and listed here too.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, unwrap } from "@/lib/api/query";

type GreyRecordCreate = components["schemas"]["GreyRecordCreate"];
type GreyKind = GreyRecordCreate["kind"];
type GreyBox = NonNullable<GreyRecordCreate["found_via"]>;

const kinds: GreyKind[] = ["thesis", "report", "register_record", "web_page"];
const boxOfKind: Record<GreyKind, GreyBox> = {
  thesis: "thesis",
  report: "organisation",
  register_record: "register",
  web_page: "website",
};
const boxes: GreyBox[] = ["thesis", "website", "organisation", "register"];

const greyKey = (reviewId: string) => ["reviews", reviewId, "grey-literature"] as const;

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

export function GreyLiteraturePanel({ reviewId }: { reviewId: string }) {
  const { t, i18n } = useTranslation();
  const api = useApi();
  const queryClient = useQueryClient();
  const entries = useQuery({
    queryKey: greyKey(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/grey-literature", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
  const add = useMutation({
    mutationFn: async (body: GreyRecordCreate) =>
      unwrap(
        await api.POST("/reviews/{review_id}/grey-literature", {
          params: { path: { review_id: reviewId } },
          body,
        }),
      ),
    // The record is in the review and in screening now: counts and queues follow.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reviews", reviewId] }),
  });

  const [kind, setKind] = useState<GreyKind>("thesis");
  const [box, setBox] = useState<GreyBox | "auto">("auto");
  const [source, setSource] = useState("");
  const [title, setTitle] = useState("");
  const [authors, setAuthors] = useState("");
  const [year, setYear] = useState("");
  const [institution, setInstitution] = useState("");
  const [url, setUrl] = useState("");
  const date = new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" });

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!title.trim() || !source.trim()) return;
    const parsedYear = Number.parseInt(year, 10);
    add.mutate(
      {
        kind,
        found_via: box === "auto" ? null : box,
        source: source.trim(),
        found_at: null,
        title: title.trim(),
        authors: authors
          .split(";")
          .map((name) => name.trim())
          .filter(Boolean),
        year: Number.isNaN(parsedYear) ? null : parsedYear,
        institution: institution.trim() || null,
        thesis_type: null,
        url: url.trim() || null,
        doi: null,
        abstract: null,
      },
      {
        onSuccess: () => {
          setTitle("");
          setAuthors("");
          setYear("");
          setUrl("");
        },
      },
    );
  }

  const field = "h-8 rounded-md border border-line-strong bg-raised px-2 text-ui text-fg";
  return (
    <section aria-labelledby="review-grey" className="space-y-2">
      <h2 id="review-grey" className="text-h3">
        {t("grey.title")}
      </h2>
      <p className="text-meta text-fg-muted">{t("grey.hint")}</p>
      <form
        aria-label={t("grey.add")}
        onSubmit={submit}
        className="grid gap-2 rounded-md border border-line bg-raised p-3 md:grid-cols-2"
      >
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.kind")}
          <select
            className={field}
            value={kind}
            onChange={(event) => {
              const next = kinds.find((k) => k === event.target.value);
              if (next) setKind(next);
            }}
          >
            {kinds.map((k) => (
              <option key={k} value={k}>
                {t(`grey.kinds.${k}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.box")}
          <select
            className={field}
            value={box}
            onChange={(event) => {
              const next = boxes.find((b) => b === event.target.value);
              setBox(next ?? "auto");
            }}
          >
            <option value="auto">
              {t("grey.boxAuto", { box: t(`grey.boxes.${boxOfKind[kind]}`) })}
            </option>
            {boxes.map((b) => (
              <option key={b} value={b}>
                {t(`grey.boxes.${b}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted md:col-span-2">
          {t("grey.titleField")}
          <Input
            value={title}
            maxLength={1000}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.source")}
          <Input
            placeholder={t("grey.sourcePlaceholder")}
            value={source}
            maxLength={64}
            onChange={(event) => {
              setSource(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.authors")}
          <Input
            placeholder={t("grey.authorsPlaceholder")}
            value={authors}
            onChange={(event) => {
              setAuthors(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.year")}
          <Input
            inputMode="numeric"
            value={year}
            maxLength={4}
            onChange={(event) => {
              setYear(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted">
          {t("grey.institution")}
          <Input
            value={institution}
            maxLength={500}
            onChange={(event) => {
              setInstitution(event.target.value);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-meta text-fg-muted md:col-span-2">
          {t("grey.url")}
          <Input
            type="url"
            value={url}
            maxLength={2000}
            onChange={(event) => {
              setUrl(event.target.value);
            }}
          />
        </label>
        <div className="flex items-center gap-3 md:col-span-2">
          <Button
            type="submit"
            variant="primary"
            disabled={!title.trim() || !source.trim() || add.isPending}
          >
            {t("grey.add")}
          </Button>
          {add.data && (
            <p role="status" className="text-meta text-fg-muted">
              {add.data.matched_existing ? t("grey.matched") : t("grey.added")}
            </p>
          )}
          {add.isError && (
            <p role="alert" className="text-meta text-danger">
              {errorText(t, add.error)}
            </p>
          )}
        </div>
      </form>
      {(entries.data ?? []).length > 0 && (
        <ul aria-label={t("grey.list")} className="space-y-1">
          {(entries.data ?? []).map((entry) => (
            <li key={entry.search_id} className="rounded-md border border-line p-2 text-ui">
              <p>
                <span className="font-semibold">{t(`grey.boxes.${entry.found_via}`)}</span>
                {" · "}
                {entry.source}
                {" · "}
                {date.format(new Date(entry.executed_at))}
                {entry.file_name && ` · ${entry.file_name}`}
              </p>
              <p className="text-meta text-fg-muted">
                {entry.records === 1 ? entry.titles[0] : t("grey.records", { n: entry.records })}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
