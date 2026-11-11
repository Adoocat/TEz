import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";

import type { ReadingStatus } from "./api";

const colors: Record<ReadingStatus, string> = {
  unread: "var(--color-status-reading-unread)",
  reading: "var(--color-status-reading-active)",
  read: "var(--color-status-reading-done)",
};

/** Hollow for unread, filled for reading and read (design 4.3, first column). */
export function ReadingDot({ status }: { status: ReadingStatus }) {
  const { t } = useTranslation();
  const color = colors[status];
  return (
    <span
      role="img"
      aria-label={t(`library.reading.${status}`)}
      title={t(`library.reading.${status}`)}
      className={cn("block size-2 shrink-0 rounded-full", status === "unread" && "border")}
      style={status === "unread" ? { borderColor: color } : { backgroundColor: color }}
    />
  );
}
