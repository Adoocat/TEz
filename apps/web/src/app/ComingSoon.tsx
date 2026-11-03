import { Hammer } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Placeholder for sections whose tasks have not landed yet. */
export function ComingSoon({ section }: { section: string }) {
  const { t } = useTranslation();
  return (
    <div className="grid h-full place-items-center p-6 text-center">
      <div className="max-w-sm space-y-2">
        <Hammer className="mx-auto size-6 text-fg-muted" aria-hidden />
        <h1 className="text-h2">{t(`nav.${section}`)}</h1>
        <p className="text-ui text-fg-muted">{t("shell.comingSoon")}</p>
        <p className="text-meta text-fg-muted">{t("shell.comingSoonDetail")}</p>
      </div>
    </div>
  );
}
