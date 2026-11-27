// Figures and tables (design 5.5, Task 55): what was kept from the PDFs, each with its label,
// caption, paper and page, and a way back to its place. Several can be compared side by side,
// their scrolling in step, and exported with their sources.
import { useQueryClient } from "@tanstack/react-query";
import { Columns2, Download, ExternalLink, MapPinOff, Pencil, Trash2, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useApi, useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { citationOf } from "@/features/reader/citation";
import { unwrap } from "@/lib/api/query";
import { fileToBase64 } from "@/lib/base64";
import { fold } from "@/lib/text";

import {
  useAssets,
  useAssetUrl,
  useDeleteAsset,
  useUpdateAsset,
  type AssetKind,
  type AssetView,
} from "./api";

type Shown = "all" | AssetKind;
const MAX_COMPARED = 4;

export function GalleryPage() {
  const { t } = useTranslation();
  const assets = useAssets();
  const remove = useDeleteAsset();
  const [shown, setShown] = useState<Shown>("all");
  const [filter, setFilter] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const [editing, setEditing] = useState<AssetView | null>(null);
  const [deleting, setDeleting] = useState<AssetView | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const exportAssets = useExport();

  const all = assets.data ?? [];
  const wanted = fold(filter.trim());
  const list = all.filter(
    (asset) =>
      (shown === "all" || asset.kind === shown) &&
      (wanted === "" ||
        fold(`${asset.label} ${asset.caption} ${asset.paper.title}`).includes(wanted)),
  );
  const picked = all.filter((asset) => chosen.includes(asset.id));

  if (comparing && picked.length > 1) {
    return (
      <Compare
        assets={picked}
        onClose={() => {
          setComparing(false);
        }}
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2">
        <h1 className="mr-2 text-h2">{t("gallery.title")}</h1>
        <Segmented
          aria-label={t("gallery.kind")}
          value={shown}
          options={[
            { value: "all", label: t("gallery.all") },
            { value: "figure", label: t("gallery.kinds.figures") },
            { value: "table", label: t("gallery.kinds.tables") },
          ]}
          onValueChange={setShown}
        />
        <Input
          type="search"
          className="w-56"
          aria-label={t("gallery.filter")}
          placeholder={t("gallery.filter")}
          value={filter}
          onChange={(event) => {
            setFilter(event.target.value);
          }}
        />
        <div className="ml-auto flex items-center gap-2">
          {chosen.length > 0 && (
            <span className="text-meta text-fg-muted">
              {t("gallery.chosen", { count: chosen.length })}
            </span>
          )}
          <Button
            size="sm"
            disabled={chosen.length < 2 || chosen.length > MAX_COMPARED}
            title={t("gallery.compareHint", { max: MAX_COMPARED })}
            onClick={() => {
              setComparing(true);
            }}
          >
            <Columns2 aria-hidden />
            {t("gallery.compare")}
          </Button>
          <Button
            size="sm"
            disabled={chosen.length === 0 || exportAssets.pending}
            onClick={() => {
              void exportAssets.run(picked).then(setSaved);
            }}
          >
            <Download aria-hidden />
            {t("gallery.export")}
          </Button>
        </div>
      </header>
      {saved && (
        <p role="status" className="border-b border-line px-4 py-1.5 text-meta text-fg-muted">
          {t("gallery.saved", { fileName: saved })}
        </p>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {assets.data && all.length === 0 && (
          <p className="max-w-lg text-ui text-fg-muted">{t("gallery.none")}</p>
        )}
        <ul
          aria-label={t("gallery.title")}
          className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3"
        >
          {list.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              chosen={chosen.includes(asset.id)}
              onChoose={(on) => {
                setChosen((now) => (on ? [...now, asset.id] : now.filter((id) => id !== asset.id)));
              }}
              onEdit={() => {
                setEditing(asset);
              }}
              onDelete={() => {
                setDeleting(asset);
              }}
            />
          ))}
        </ul>
      </div>
      {editing && (
        <EditAsset
          asset={editing}
          onClose={() => {
            setEditing(null);
          }}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={t("gallery.deleteTitle", {
          label: deleting && deleting.label !== "" ? deleting.label : t("gallery.untitled"),
        })}
        description={t("gallery.deleteText")}
        confirmLabel={t("gallery.delete")}
        cancelLabel={t("gallery.cancel")}
        onConfirm={() => {
          if (deleting) remove.mutate(deleting.id);
          setChosen((now) => now.filter((id) => id !== deleting?.id));
          setDeleting(null);
        }}
        onCancel={() => {
          setDeleting(null);
        }}
      />
    </div>
  );
}

/** "Kim et al. 2024, p. 7": where a figure or table comes from. */
function useSource() {
  const { t } = useTranslation();
  return (asset: AssetView) =>
    t("gallery.source", { citation: citationOf(asset.paper, t), page: asset.page });
}

function AssetCard({
  asset,
  chosen,
  onChoose,
  onEdit,
  onDelete,
}: {
  asset: AssetView;
  chosen: boolean;
  onChoose: (on: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const url = useAssetUrl(asset.id);
  const source = useSource();
  const name = asset.label || t("gallery.untitled");
  return (
    <li
      aria-label={name}
      className="flex flex-col overflow-hidden rounded-md border border-line bg-raised"
    >
      <div className="relative grid h-40 place-items-center border-b border-line bg-white">
        {url && <img src={url} alt={name} className="max-h-full max-w-full object-contain" />}
        <label className="absolute top-2 left-2 rounded-xs bg-raised/90 p-1">
          <input
            type="checkbox"
            aria-label={t("gallery.choose", { label: name })}
            checked={chosen}
            onChange={(event) => {
              onChoose(event.target.checked);
            }}
          />
        </label>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-2">
        <p className="flex items-baseline gap-2">
          <span className="font-medium">{name}</span>
          <span className="text-meta text-fg-muted">{t(`gallery.kinds.${asset.kind}`)}</span>
        </p>
        {asset.caption && <p className="line-clamp-3 text-meta">{asset.caption}</p>}
        <p className="text-meta text-fg-muted">{source(asset)}</p>
        {asset.anchor_status === "lost" && (
          <p className="flex items-center gap-1 text-meta text-warning">
            <MapPinOff aria-hidden className="size-3.5" />
            {t("gallery.lost")}
          </p>
        )}
        <div className="mt-auto flex items-center gap-1 pt-1">
          <Link
            to={`/reader/${asset.attachment_id}?anchor=${asset.anchor_id}`}
            className="flex items-center gap-1 text-meta text-primary hover:underline"
          >
            <ExternalLink aria-hidden className="size-3.5" />
            {t("gallery.open")}
          </Link>
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            aria-label={t("gallery.edit", { label: name })}
            onClick={onEdit}
          >
            <Pencil aria-hidden />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={t("gallery.deleteNamed", { label: name })}
            onClick={onDelete}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
    </li>
  );
}

/** Side by side, their scrolling in step: the same place in each, as far as it goes. */
function Compare({ assets, onClose }: { assets: AssetView[]; onClose: () => void }) {
  const { t } = useTranslation();
  const panes = useRef<(HTMLDivElement | null)[]>([]);
  const moving = useRef(false);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2">
        <h1 className="text-h2">{t("gallery.comparing", { count: assets.length })}</h1>
        <Button size="sm" className="ml-auto" onClick={onClose}>
          <X aria-hidden />
          {t("gallery.back")}
        </Button>
      </header>
      <div
        className="grid min-h-0 flex-1 gap-px bg-line"
        style={{ gridTemplateColumns: `repeat(${String(assets.length)}, minmax(0, 1fr))` }}
      >
        {assets.map((asset, index) => (
          <ComparePane
            key={asset.id}
            asset={asset}
            paneRef={(element) => {
              panes.current[index] = element;
            }}
            onScroll={(from) => {
              if (moving.current) return;
              moving.current = true;
              const share = from.scrollTop / Math.max(1, from.scrollHeight - from.clientHeight);
              for (const pane of panes.current) {
                if (pane && pane !== from) {
                  pane.scrollTop = share * (pane.scrollHeight - pane.clientHeight);
                }
              }
              requestAnimationFrame(() => {
                moving.current = false;
              });
            }}
          />
        ))}
      </div>
    </div>
  );
}

function ComparePane({
  asset,
  paneRef,
  onScroll,
}: {
  asset: AssetView;
  paneRef: (element: HTMLDivElement | null) => void;
  onScroll: (from: HTMLDivElement) => void;
}) {
  const { t } = useTranslation();
  const url = useAssetUrl(asset.id);
  const source = useSource();
  const name = asset.label || t("gallery.untitled");
  return (
    <section aria-label={name} className="flex min-h-0 flex-col bg-raised">
      <p className="border-b border-line px-3 py-1.5 text-meta">
        <span className="font-medium">{name}</span>
        <span className="text-fg-muted"> · {source(asset)}</span>
      </p>
      <div
        ref={paneRef}
        data-testid="compare-pane"
        className="min-h-0 flex-1 overflow-auto bg-white p-2"
        onScroll={(event) => {
          onScroll(event.currentTarget);
        }}
      >
        {url && <img src={url} alt={name} className="w-full" />}
      </div>
    </section>
  );
}

function EditAsset({ asset, onClose }: { asset: AssetView; onClose: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateAsset();
  const [kind, setKind] = useState(asset.kind);
  const [label, setLabel] = useState(asset.label);
  const [caption, setCaption] = useState(asset.caption);
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[15%] left-1/2 z-[var(--z-dialog)] w-112 max-w-[92vw] -translate-x-1/2 space-y-3 rounded-lg border border-line bg-raised p-4 shadow-popover"
        >
          <Dialog.Title className="text-h3">{t("gallery.editTitle")}</Dialog.Title>
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              update.mutate(
                { id: asset.id, patch: { kind, label: label.trim(), caption: caption.trim() } },
                { onSuccess: onClose },
              );
            }}
          >
            <Segmented
              aria-label={t("gallery.kind")}
              value={kind}
              options={[
                { value: "figure", label: t("gallery.kinds.figure") },
                { value: "table", label: t("gallery.kinds.table") },
              ]}
              onValueChange={setKind}
            />
            <label className="block space-y-1">
              <span className="text-meta text-fg-muted">{t("gallery.label")}</span>
              <Input
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
            <div className="flex justify-end gap-2">
              <Button type="button" onClick={onClose}>
                {t("gallery.cancel")}
              </Button>
              <Button type="submit" variant="primary" disabled={update.isPending}>
                {t("gallery.saveChanges")}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const escapeHtml = (text: string) =>
  text.replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] ?? c,
  );

/** The chosen items as one HTML page: each picture with its label, caption and source. */
function useExport() {
  const { t, i18n } = useTranslation();
  const { platform } = useBackend();
  const source = useSource();
  const api = useAssetBlobFetcher();
  const [pending, setPending] = useState(false);
  return {
    pending,
    async run(assets: AssetView[]): Promise<string> {
      setPending(true);
      try {
        const parts = await Promise.all(
          assets.map(async (asset) => {
            const data = await fileToBase64(await api(asset.id));
            const name = escapeHtml(asset.label || t("gallery.untitled"));
            return [
              "<figure>",
              `<img src="data:image/png;base64,${data}" alt="${name}">`,
              `<figcaption><strong>${name}</strong>${asset.caption ? ` ${escapeHtml(asset.caption)}` : ""}`,
              `<br><small>${escapeHtml(source(asset))}</small></figcaption>`,
              "</figure>",
            ].join("");
          }),
        );
        const title = escapeHtml(t("gallery.title"));
        const page = [
          "<!doctype html>",
          `<html lang="${i18n.language}"><head><meta charset="utf-8"><title>${title}</title>`,
          "<style>body{font-family:system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem}",
          "figure{margin:0 0 2rem}img{max-width:100%;border:1px solid #ddd}figcaption{margin-top:.5rem}</style>",
          `</head><body><h1>${title}</h1>`,
          ...parts,
          "</body></html>",
        ].join("\n");
        const fileName = t("gallery.fileName");
        await platform.saveFile(fileName, page, "text/html");
        return fileName;
      } finally {
        setPending(false);
      }
    },
  };
}

/** Fetches a picture for export, reusing the copy already on screen. */
function useAssetBlobFetcher() {
  const api = useApi();
  const queryClient = useQueryClient();
  return async (id: string): Promise<Blob> => {
    const cached = queryClient.getQueryData<Blob>(["assets", id, "image"]);
    if (cached) return cached;
    return unwrap(
      await api.GET("/assets/{asset_id}/image", {
        params: { path: { asset_id: id } },
        parseAs: "blob",
      }),
    );
  };
}
