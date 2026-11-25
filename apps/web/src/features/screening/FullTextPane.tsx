// Full-text screening's left side (design 5.2, Task 33): the record's PDF in the reader, or,
// without one, a way to look for a free copy. A report that cannot be obtained is decided
// as "full text not retrieved", which PRISMA counts in a box of its own.
import { useQueryClient } from "@tanstack/react-query";
import { FileSearch } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { useFindOpenAccess } from "@/features/files/api";
import { useJobsStore } from "@/features/jobs/store";
import { readablePdf } from "@/features/library/api";
import { PdfReader } from "@/features/reader/PdfReader";

import { screeningKeys, type ScreeningRecord } from "./api";

export function FullTextPane({ reviewId, record }: { reviewId: string; record: ScreeningRecord }) {
  const { t } = useTranslation();
  const pdf = readablePdf(record);
  return (
    <section
      aria-label={t("screening.fullText.label")}
      className="flex min-w-0 flex-[3] basis-0 flex-col border-r border-line bg-canvas"
    >
      {pdf ? (
        <PdfReader key={pdf.id} attachmentId={pdf.id} embedded />
      ) : (
        <NoPdf key={record.paper_id} reviewId={reviewId} paperId={record.paper_id} />
      )}
    </section>
  );
}

function NoPdf({ reviewId, paperId }: { reviewId: string; paperId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const find = useFindOpenAccess();
  const jobs = useJobsStore((state) => state.jobs);
  const started = find.data?.job_ids ?? [];
  const finished =
    started.length > 0 &&
    started.every((id) => ["done", "failed", "cancelled"].includes(jobs[id]?.status ?? ""));
  const failed = started.some((id) => jobs[id]?.status === "failed");

  // A fetched PDF belongs to the record now: load it again to show the reader.
  useEffect(() => {
    if (finished) {
      void queryClient.invalidateQueries({
        queryKey: screeningKeys.record(reviewId, "full_text", paperId),
      });
    }
  }, [finished, queryClient, reviewId, paperId]);

  const status = find.isError
    ? t("screening.fullText.findFailed")
    : find.data?.no_source
      ? t("screening.fullText.noSource")
      : finished
        ? failed
          ? t("screening.fullText.notFound")
          : null
        : started.length > 0
          ? t("screening.fullText.looking")
          : null;

  return (
    <div className="grid h-full place-items-center p-6 text-center">
      <div className="max-w-sm space-y-3">
        <FileSearch aria-hidden className="mx-auto size-8 text-fg-muted" />
        <h2 className="text-h3">{t("screening.fullText.noPdf")}</h2>
        <p className="text-ui text-fg-muted">{t("screening.fullText.noPdfHint")}</p>
        <Button
          variant="primary"
          disabled={find.isPending || (started.length > 0 && !finished)}
          onClick={() => {
            find.mutate([paperId]);
          }}
        >
          {t("screening.fullText.find")}
        </Button>
        {status && (
          <p role="status" className="text-meta text-fg-muted">
            {status}
          </p>
        )}
      </div>
    </div>
  );
}
