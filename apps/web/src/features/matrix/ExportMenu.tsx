// "Export" on the matrix toolbar (design 5.4, Task 54): CSV, Excel or Markdown, with each
// value's passages and pages. The file's words are the app's language.
import { Download } from "lucide-react";
import { DropdownMenu } from "radix-ui";
import { useTranslation } from "react-i18next";

import { useBackend } from "@/app/backend";
import { base64ToBytes } from "@/lib/base64";

import { useExportMatrix, type ExportFormat } from "./api";

const EXTENSION: Record<ExportFormat, string> = { csv: "csv", xlsx: "xlsx", md: "md" };

/** A file name from the matrix's: Turkish letters kept, characters Windows refuses dropped. */
export function fileNameOf(name: string, format: ExportFormat): string {
  const base =
    name
      .replace(/[\\/:*?"<>|]+/g, " ")
      .replace(/\s+/g, " ")
      .trim() || "matrix";
  return `${base}.${EXTENSION[format]}`;
}

export function ExportMenu({
  matrixId,
  name,
  onSaved,
}: {
  matrixId: string;
  name: string;
  onSaved: (fileName: string) => void;
}) {
  const { t } = useTranslation();
  const { platform } = useBackend();
  const exported = useExportMatrix(matrixId);

  async function save(format: ExportFormat) {
    const file = await exported.mutateAsync({
      format,
      labels: {
        paper: t("matrix.export.paper"),
        title: t("matrix.export.title"),
        year: t("matrix.export.year"),
        quality: t("matrix.export.quality"),
        evidence: t("matrix.export.evidence"),
        page: t("matrix.export.page"),
        et_al: t("matrix.export.etAl"),
        yes: t("matrix.yes"),
        no: t("matrix.no"),
      },
    });
    const fileName = fileNameOf(name, format);
    await platform.saveFile(fileName, base64ToBytes(file.content_base64), file.mime_type);
    onSaved(fileName);
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        disabled={exported.isPending}
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line bg-raised px-3 text-ui hover:bg-hovered disabled:opacity-50"
      >
        <Download aria-hidden className="size-4" />
        {t("matrix.export.action")}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-[var(--z-popover)] min-w-44 rounded-md border border-line bg-raised p-1 text-ui shadow-popover"
        >
          {(["xlsx", "csv", "md"] as const).map((format) => (
            <DropdownMenu.Item
              key={format}
              className="cursor-default rounded-xs px-2 py-1.5 outline-none data-highlighted:bg-hovered"
              onSelect={() => {
                void save(format).catch(() => undefined);
              }}
            >
              {t(`matrix.export.${format}`)}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
