// The `?` overlay: every shortcut, by context, read from the same maps as the handlers.
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { shortcutContexts, shortcutMaps, type Shortcut } from "@/lib/shortcuts/maps";
import { ShortcutKeys } from "@/lib/shortcuts/ShortcutKeys";
import { useShortcuts } from "@/lib/shortcuts/useShortcuts";

export function ShortcutOverlay() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  useShortcuts("global", {
    help: () => {
      setOpen((now) => !now);
    },
  });

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content className="fixed top-[10vh] left-1/2 z-[var(--z-dialog)] max-h-[80vh] w-[40rem] max-w-[90vw] -translate-x-1/2 overflow-y-auto rounded-lg border border-line bg-raised p-4 shadow-popover">
          <Dialog.Title className="text-h3">{t("shortcuts.title")}</Dialog.Title>
          <Dialog.Description className="mt-1 text-meta text-fg-muted">
            {t("shortcuts.description")}
          </Dialog.Description>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {shortcutContexts.map((context) => (
              <section key={context} aria-labelledby={`shortcuts-${context}`}>
                <h3 id={`shortcuts-${context}`} className="mb-1 text-ui font-semibold">
                  {t(`shortcuts.contexts.${context}`)}
                </h3>
                <dl className="space-y-1">
                  {(shortcutMaps[context] as readonly Shortcut[]).map(({ id }) => (
                    <div key={id} className="flex items-center justify-between gap-3 text-ui">
                      <dt>{t(`shortcuts.actions.${context}.${id}`)}</dt>
                      <dd>
                        <ShortcutKeys context={context} id={id as never} />
                      </dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
