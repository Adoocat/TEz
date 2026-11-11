import { AlertDialog } from "radix-ui";

import { Button } from "./button";

/** Asks before something that cannot be undone. The confirm button says what it does. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <AlertDialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <AlertDialog.Content className="fixed top-1/4 left-1/2 z-[var(--z-dialog)] w-96 max-w-[90vw] -translate-x-1/2 space-y-3 rounded-lg border border-line bg-raised p-4 shadow-popover">
          <AlertDialog.Title className="text-h3">{title}</AlertDialog.Title>
          <AlertDialog.Description className="text-ui text-fg-muted">
            {description}
          </AlertDialog.Description>
          <div className="flex justify-end gap-2">
            <AlertDialog.Cancel asChild>
              <Button>{cancelLabel}</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <Button variant="danger" onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
