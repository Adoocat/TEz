// "Save as figure or table" in the reader (design 5.5, Task 55): the area just marked, with
// what it is, its label as the paper has it, and its caption.
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";
import type { PdfRect } from "@/lib/pdfGeometry";

import { useAddAsset, type AssetKind, type AssetView } from "./api";

export interface MarkedArea {
  page: number;
  rect: PdfRect;
  /** The area as drawn on screen, as a PNG data URL. */
  image: string;
}

export function SaveAsset({
  attachmentId,
  area,
  onDone,
  onCancel,
}: {
  attachmentId: string;
  area: MarkedArea;
  onDone: (asset: AssetView) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const add = useAddAsset(attachmentId);
  const [kind, setKind] = useState<AssetKind>("figure");
  const [label, setLabel] = useState("");
  const [caption, setCaption] = useState("");

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[10%] left-1/2 z-[var(--z-dialog)] max-h-[85vh] w-112 max-w-[92vw] -translate-x-1/2 space-y-3 overflow-y-auto rounded-lg border border-line bg-raised p-4 shadow-popover"
        >
          <Dialog.Title className="text-h3">{t("gallery.save.title")}</Dialog.Title>
          <img
            src={area.image}
            alt={t("gallery.save.preview")}
            className="max-h-56 w-full rounded-md border border-line bg-white object-contain"
          />
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              add.mutate(
                {
                  kind,
                  label: label.trim(),
                  caption: caption.trim(),
                  page: area.page,
                  rect: area.rect,
                  image_base64: area.image.slice(area.image.indexOf(",") + 1),
                },
                { onSuccess: onDone },
              );
            }}
          >
            <fieldset className="flex gap-2">
              <legend className="sr-only">{t("gallery.kind")}</legend>
              {(["figure", "table"] as const).map((option) => (
                <label
                  key={option}
                  className="flex cursor-pointer items-center gap-1.5 rounded-md border border-line px-2 py-1 text-ui has-checked:border-primary has-checked:bg-hovered"
                >
                  <input
                    type="radio"
                    name="asset-kind"
                    className="sr-only"
                    checked={kind === option}
                    onChange={() => {
                      setKind(option);
                    }}
                  />
                  {t(`gallery.kinds.${option}`)}
                </label>
              ))}
            </fieldset>
            <label className="block space-y-1">
              <span className="text-meta text-fg-muted">{t("gallery.label")}</span>
              <Input
                autoFocus
                placeholder={t(`gallery.labelHint.${kind}`)}
                value={label}
                onChange={(event) => {
                  setLabel(event.target.value);
                }}
              />
            </label>
            <label className="block space-y-1">
              <span className="text-meta text-fg-muted">{t("gallery.caption")}</span>
              <textarea
                rows={3}
                className="w-full rounded-md border border-line bg-raised px-2 py-1.5 text-ui"
                value={caption}
                onChange={(event) => {
                  setCaption(event.target.value);
                }}
              />
            </label>
            {add.error && (
              <p role="alert" className="text-meta text-danger">
                {t(`errors.${add.error instanceof ApiError ? add.error.code : "unknown"}`, {
                  defaultValue: t("errors.unknown"),
                })}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Button type="button" onClick={onCancel}>
                {t("gallery.cancel")}
              </Button>
              <Button type="submit" variant="primary" disabled={add.isPending}>
                {t("gallery.save.action")}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** The marked area as the page canvas shows it, cut out as a PNG. */
export function cutOut(
  canvas: HTMLCanvasElement,
  box: { left: number; top: number; width: number; height: number },
): string | null {
  const ratio = canvas.width / Math.max(1, canvas.clientWidth);
  const width = Math.max(1, Math.round(box.width * ratio));
  const height = Math.max(1, Math.round(box.height * ratio));
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const context = out.getContext("2d");
  if (!context) return null;
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  context.drawImage(canvas, box.left * ratio, box.top * ratio, width, height, 0, 0, width, height);
  return out.toDataURL("image/png");
}
