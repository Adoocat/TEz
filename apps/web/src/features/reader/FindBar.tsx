// Search inside the open document. The backend says which pages match and how often (its text
// covers the whole file, read or not); the pages on screen mark the matches themselves.
import { ChevronDown, ChevronUp, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import type { FindResults } from "./api";

export function FindBar({
  query,
  results,
  position,
  onQuery,
  onStep,
  onClose,
}: {
  query: string;
  results: FindResults | undefined;
  /** Which match is current, from 1; 0 when there is none. */
  position: number;
  onQuery: (query: string) => void;
  onStep: (direction: 1 | -1) => void;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const number = (value: number) => value.toLocaleString(i18n.language);
  const message =
    query.trim() === "" || !results
      ? ""
      : results.text === "pending"
        ? t("reader.find.pending")
        : results.text === "none"
          ? t("reader.find.noText")
          : results.total === 0
            ? t("reader.find.none")
            : t("reader.find.position", {
                current: number(position),
                total: number(results.total),
              });
  const none = !results || results.total === 0;
  return (
    <div
      role="search"
      className="flex items-center gap-2 border-b border-line bg-surface px-4 py-1.5"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <Input
        type="search"
        // The bar appears because the user asked to search.
        autoFocus
        className="h-7 w-72 max-w-full"
        aria-label={t("reader.find.label")}
        placeholder={t("reader.find.placeholder")}
        value={query}
        onChange={(event) => {
          onQuery(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key !== "Enter") return;
          event.preventDefault();
          onStep(event.shiftKey ? -1 : 1);
        }}
      />
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("reader.find.previous")}
        disabled={none}
        onClick={() => {
          onStep(-1);
        }}
      >
        <ChevronUp />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("reader.find.next")}
        disabled={none}
        onClick={() => {
          onStep(1);
        }}
      >
        <ChevronDown />
      </Button>
      <span role="status" className="text-meta text-fg-muted tabular-nums">
        {message}
      </span>
      <div className="flex-1" />
      <Button variant="ghost" size="icon" aria-label={t("reader.find.close")} onClick={onClose}>
        <X />
      </Button>
    </div>
  );
}
