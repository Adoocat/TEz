// Drop PDFs anywhere on the window to add them to the library (design 4.3, 4.6). Each file
// becomes a notice in the corner: added to the inbox, already in the library, or why not.
import { CheckCircle2, CircleAlert, Copy, FileDown, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/query";

import { isPdf, useUploadPdf } from "./api";
import { useUploadStore, type UploadNotice } from "./store";

// Successful notices fade on their own; failures wait to be read.
const NOTICE_MS = 6000;

function hasFiles(event: DragEvent): boolean {
  return event.dataTransfer?.types.includes("Files") ?? false;
}

/** Listens on the whole window; shows a veil while files are dragged over it. */
export function PdfDrop() {
  const { t } = useTranslation();
  const { mutateAsync: uploadPdf } = useUploadPdf();
  const { start, update } = useUploadStore();
  const [dragging, setDragging] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    // dragenter/dragleave fire for every child element; count them to know when we left.
    let depth = 0;
    const enter = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      depth += 1;
      setDragging(true);
    };
    const leave = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      depth = Math.max(0, depth - 1);
      if (depth === 0) setDragging(false);
    };
    const over = (event: DragEvent) => {
      // Without this the browser opens the dropped PDF instead of handing it to us.
      if (hasFiles(event)) event.preventDefault();
    };
    const drop = (event: DragEvent) => {
      depth = 0;
      setDragging(false);
      // A drop handled by a dialog's own drop zone (the import dialog) is not ours.
      if (!hasFiles(event) || event.defaultPrevented) return;
      event.preventDefault();
      const pdfs = [...(event.dataTransfer?.files ?? [])].filter(isPdf);
      void uploadAll(pdfs);
    };

    async function uploadAll(files: File[]) {
      // One at a time: the backend hashes and copies each file; order is the user's order.
      for (const file of files) {
        const id = start(file.name);
        try {
          const added = await uploadPdf({ file });
          update(id, { state: added.status });
          // A single PDF is opened to read (design 4.6); several only go to the inbox.
          if (files.length === 1) void navigate(`/reader/${added.attachment_id}`);
        } catch (error) {
          update(id, {
            state: "failed",
            errorCode: error instanceof ApiError ? error.code : "unknown",
            errorParams: error instanceof ApiError ? error.params : {},
          });
        }
      }
    }

    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [start, update, uploadPdf, navigate]);

  return (
    <>
      {dragging && (
        <div
          aria-hidden
          className="pointer-events-none fixed inset-0 z-[var(--z-toast)] grid place-items-center bg-primary-soft/80"
        >
          <p className="flex items-center gap-2 rounded-lg border border-primary bg-raised px-4 py-3 text-ui shadow-popover">
            <FileDown aria-hidden className="size-5 text-primary" />
            {t("files.dropToAdd")}
          </p>
        </div>
      )}
      <UploadNotices />
    </>
  );
}

function UploadNotices() {
  const notices = useUploadStore((state) => state.notices);
  if (notices.length === 0) return null;
  return (
    <ul
      aria-live="polite"
      className="fixed right-3 bottom-9 z-[var(--z-toast)] w-80 max-w-[90vw] space-y-2"
    >
      {notices.map((notice) => (
        <NoticeItem key={notice.id} notice={notice} />
      ))}
    </ul>
  );
}

function NoticeItem({ notice }: { notice: UploadNotice }) {
  const { t } = useTranslation();
  const dismiss = useUploadStore((state) => state.dismiss);
  const settled = notice.state === "added" || notice.state === "duplicate";

  useEffect(() => {
    if (!settled) return;
    const timer = setTimeout(() => {
      dismiss(notice.id);
    }, NOTICE_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [settled, dismiss, notice.id]);

  const icon = {
    uploading: <Loader2 aria-hidden className="size-4 animate-spin text-fg-muted" />,
    added: <CheckCircle2 aria-hidden className="size-4 text-success" />,
    duplicate: <Copy aria-hidden className="size-4 text-fg-muted" />,
    failed: <CircleAlert aria-hidden className="size-4 text-danger" />,
  }[notice.state];
  const message =
    notice.state === "failed"
      ? t(`errors.${notice.errorCode ?? "unknown"}`, {
          ...notice.errorParams,
          defaultValue: t("errors.unknown"),
        })
      : t(`files.notice.${notice.state}`);

  return (
    <li className="flex items-start gap-2 rounded-md border border-line bg-raised p-2 text-meta shadow-popover">
      <span className="mt-0.5">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-fg">{notice.fileName}</p>
        <p className="text-fg-muted">{message}</p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="size-6"
        aria-label={t("files.dismiss")}
        onClick={() => {
          dismiss(notice.id);
        }}
      >
        <X />
      </Button>
    </li>
  );
}
