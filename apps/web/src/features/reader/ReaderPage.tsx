// The reader screen (design 4.5): the open documents as tabs, and the one being read.
import { BookOpen, X } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, NavLink, useNavigate, useParams } from "react-router";

import { useLayoutStore } from "@/app/layout/uiStore";
import { useAttachment } from "@/features/files/api";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";

import { PdfReader } from "./PdfReader";
import { useReaderTabs, type ReaderTab } from "./store";

function addressOf(tab: ReaderTab | null): string {
  if (!tab) return "/reader";
  return `/reader/${tab.attachmentId}${tab.page > 1 ? `?page=${String(tab.page)}` : ""}`;
}

export function ReaderPage() {
  const { t } = useTranslation();
  const { attachmentId } = useParams();
  const { tabs, activeId } = useReaderTabs();
  const setFocus = useLayoutStore((state) => state.setFocus);
  useEffect(
    () => () => {
      setFocus(false);
    },
    [setFocus],
  );

  if (attachmentId) return <OpenReader key={attachmentId} attachmentId={attachmentId} />;
  // The navigation's "Reader" goes back to what was being read.
  const last = tabs.find((tab) => tab.attachmentId === activeId) ?? tabs[0];
  if (last) return <Navigate to={addressOf(last)} replace />;
  return (
    <div className="grid h-full place-items-center p-6 text-center">
      <div className="max-w-sm space-y-2">
        <BookOpen aria-hidden className="mx-auto size-6 text-fg-muted" />
        <h1 className="text-h2">{t("reader.title")}</h1>
        <p className="text-ui text-fg-muted">{t("reader.nothingOpen")}</p>
      </div>
    </div>
  );
}

function OpenReader({ attachmentId }: { attachmentId: string }) {
  const { t } = useTranslation();
  const attachment = useAttachment(attachmentId);
  const openTab = useReaderTabs((state) => state.open);
  const closeTab = useReaderTabs((state) => state.close);
  const focus = useLayoutStore((state) => state.focus);
  const name = attachment.data?.file_name;
  const gone =
    attachment.error instanceof ApiError && attachment.error.code === "attachment.not_found";

  useEffect(() => {
    if (attachment.isSuccess) openTab(attachmentId, name ?? t("reader.title"));
  }, [attachment.isSuccess, attachmentId, name, openTab, t]);
  // A tab remembered from another library, or of a deleted file.
  useEffect(() => {
    if (gone) closeTab(attachmentId);
  }, [gone, attachmentId, closeTab]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {!focus && <Tabs current={attachmentId} />}
      {gone ? (
        <p role="alert" className="p-6 text-ui text-fg-muted">
          {t("reader.gone")}
        </p>
      ) : (
        <div className="min-h-0 flex-1">
          <PdfReader attachmentId={attachmentId} />
        </div>
      )}
    </div>
  );
}

function Tabs({ current }: { current: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tabs, close } = useReaderTabs();
  if (tabs.length === 0) return null;
  return (
    <nav
      aria-label={t("reader.tabs")}
      className="flex shrink-0 overflow-x-auto border-b border-line bg-surface"
    >
      {tabs.map((tab) => (
        <div
          key={tab.attachmentId}
          className={cn(
            "flex max-w-60 min-w-0 items-center gap-1 border-r border-line pr-1",
            tab.attachmentId === current
              ? "border-t-2 border-t-primary bg-canvas"
              : "border-t-2 border-t-transparent",
          )}
        >
          <NavLink
            to={addressOf(tab)}
            className="min-w-0 truncate py-1.5 pl-3 text-ui text-fg hover:underline"
            title={tab.title}
          >
            {tab.title}
          </NavLink>
          <button
            type="button"
            aria-label={t("reader.closeTab", { title: tab.title })}
            className="grid size-6 shrink-0 place-items-center rounded-xs text-fg-muted hover:bg-hovered hover:text-fg [&_svg]:size-3"
            onClick={() => {
              const next = close(tab.attachmentId);
              if (tab.attachmentId === current) void navigate(addressOf(next));
            }}
          >
            <X aria-hidden />
          </button>
        </div>
      ))}
    </nav>
  );
}
