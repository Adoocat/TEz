// The decision bar (design 5.2, bottom): Include I · Exclude E (+ reason) · Maybe M ·
// Skip → · Undo U · Note N. Every button shows its key, read from the screening map.
import { DropdownMenu } from "radix-ui";
import {
  ChevronDown,
  CircleCheck,
  CircleHelp,
  CircleX,
  NotebookPen,
  SkipForward,
  Undo2,
  Ban,
} from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { ariaShortcut, ShortcutKeys } from "@/lib/shortcuts/ShortcutKeys";
import type { ShortcutId } from "@/lib/shortcuts/maps";

import type { StageCriterion } from "./api";

type Action = ShortcutId<"screening">;

function Hint({ id }: { id: Action }) {
  return <ShortcutKeys context="screening" id={id} className="ml-1" />;
}

function BarButton({
  id,
  label,
  icon,
  variant = "secondary",
  disabled,
  onClick,
}: {
  id: Action;
  label: string;
  icon: ReactNode;
  variant?: "secondary" | "ghost" | "primary";
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      variant={variant}
      // The key is announced through aria-keyshortcuts, not as part of the name.
      aria-label={label}
      aria-keyshortcuts={ariaShortcut("screening", id)}
      disabled={disabled}
      onClick={onClick}
    >
      {icon}
      {label}
      <Hint id={id} />
    </Button>
  );
}

export function DecisionBar({
  exclusions,
  excludeOpen,
  onExcludeOpenChange,
  busy,
  canDecide,
  fullText,
  onInclude,
  onExclude,
  onMaybe,
  onNotRetrieved,
  onSkip,
  onUndo,
  onNote,
}: {
  exclusions: readonly StageCriterion[];
  excludeOpen: boolean;
  onExcludeOpenChange: (open: boolean) => void;
  busy: boolean;
  canDecide: boolean;
  fullText: boolean;
  onInclude: () => void;
  onExclude: (criterion: StageCriterion) => void;
  onMaybe: () => void;
  onNotRetrieved: () => void;
  onSkip: () => void;
  onUndo: () => void;
  onNote: () => void;
}) {
  const { t } = useTranslation();
  const off = busy || !canDecide;

  return (
    <div
      role="toolbar"
      aria-label={t("screening.bar.label")}
      className="flex flex-wrap items-center gap-2 border-t border-line bg-surface px-4 py-2"
    >
      <BarButton
        id="include"
        variant="primary"
        label={t("screening.bar.include")}
        icon={<CircleCheck aria-hidden />}
        disabled={off}
        onClick={onInclude}
      />
      <DropdownMenu.Root open={excludeOpen} onOpenChange={onExcludeOpenChange}>
        <DropdownMenu.Trigger asChild disabled={off}>
          <Button
            variant="secondary"
            aria-label={t("screening.bar.exclude")}
            aria-keyshortcuts={ariaShortcut("screening", "exclude")}
          >
            <CircleX aria-hidden className="text-danger" />
            {t("screening.bar.exclude")}
            <Hint id="exclude" />
            <ChevronDown aria-hidden />
          </Button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            side="top"
            align="start"
            className="z-[var(--z-dialog)] max-w-md min-w-64 rounded-md border border-line bg-raised p-1 shadow-popover"
          >
            <DropdownMenu.Label className="px-2 py-1 text-meta text-fg-muted">
              {t("screening.bar.reason")}
            </DropdownMenu.Label>
            {exclusions.length === 0 && (
              <p className="px-2 py-1 text-meta text-fg-muted">
                {t("screening.criteria.noExclusion")}
              </p>
            )}
            {exclusions.map((criterion) => (
              <DropdownMenu.Item
                key={criterion.id}
                onSelect={() => {
                  onExclude(criterion);
                }}
                className="flex cursor-default items-start gap-2 rounded-xs px-2 py-1 text-ui outline-none data-highlighted:bg-hovered"
              >
                {criterion.shortcut !== null ? (
                  <kbd className="rounded-xs border border-kbd-line bg-kbd px-1.5 font-mono text-meta">
                    {criterion.shortcut}
                  </kbd>
                ) : (
                  <span className="w-5" />
                )}
                <span className="font-mono text-meta text-danger">{criterion.code}</span>
                <span className="min-w-0 flex-1">{criterion.text}</span>
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <BarButton
        id="maybe"
        label={t("screening.bar.maybe")}
        icon={<CircleHelp aria-hidden className="text-warning" />}
        disabled={off}
        onClick={onMaybe}
      />
      {fullText && (
        <Button variant="secondary" disabled={off} onClick={onNotRetrieved}>
          <Ban aria-hidden />
          {t("screening.bar.notRetrieved")}
        </Button>
      )}
      <span aria-hidden className="mx-1 h-6 border-l border-line" />
      <BarButton
        id="skip"
        variant="ghost"
        label={t("screening.bar.skip")}
        icon={<SkipForward aria-hidden />}
        disabled={!canDecide}
        onClick={onSkip}
      />
      <BarButton
        id="undo"
        variant="ghost"
        label={t("screening.bar.undo")}
        icon={<Undo2 aria-hidden />}
        disabled={busy}
        onClick={onUndo}
      />
      <BarButton
        id="note"
        variant="ghost"
        label={t("screening.bar.note")}
        icon={<NotebookPen aria-hidden />}
        disabled={!canDecide}
        onClick={onNote}
      />
    </div>
  );
}
