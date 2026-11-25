// The shell every screen shares (design-prompt §3): top bar, navigation rail, context
// sidebar, main area, optional inspector, status bar.
import {
  BookOpen,
  FileCheck2,
  FileOutput,
  LayoutDashboard,
  Library,
  ListChecks,
  Moon,
  NotebookPen,
  PanelLeft,
  PanelRight,
  Search,
  Settings,
  Sun,
  Table2,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { PdfDrop } from "@/features/files/PdfDrop";
import { useJobEvents } from "@/features/jobs/useJobEvents";
import { useOpenRequests } from "@/features/open/useOpenRequests";
import { LibraryInspector } from "@/features/library/LibraryInspector";
import { LibrarySidebar } from "@/features/library/LibrarySidebar";
import { NotesInspector } from "@/features/notes/NotesInspector";
import { NotesSidebar } from "@/features/notes/NotesSidebar";
import { ReaderInspector } from "@/features/reader/ReaderInspector";
import { ReviewPicker } from "@/features/reviews/ReviewPicker";
import { SearchInspector } from "@/features/search/SearchInspector";
import { useSettings, useUpdateSettings } from "@/features/settings/api";
import { SettingsNav } from "@/features/settings/SettingsNav";
import { ShortcutOverlay } from "@/features/shortcuts/ShortcutOverlay";
import { PreferencesSync } from "@/features/settings/PreferencesSync";
import { cn } from "@/lib/cn";
import { cachedTheme, resolveTheme } from "@/lib/preferences";
import { bindingLabel } from "@/lib/shortcuts/keys";
import { shortcut } from "@/lib/shortcuts/maps";
import { useShortcuts } from "@/lib/shortcuts/useShortcuts";

import { StatusBar } from "./StatusBar";
import { useLayoutStore } from "./uiStore";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label:
    | "review"
    | "search"
    | "library"
    | "screening"
    | "reader"
    | "notes"
    | "matrix"
    | "export"
    | "jobs"
    | "settings";
}

const mainNav: NavItem[] = [
  { to: "/review", icon: LayoutDashboard, label: "review" },
  { to: "/search", icon: Search, label: "search" },
  { to: "/library", icon: Library, label: "library" },
  { to: "/screening", icon: FileCheck2, label: "screening" },
  { to: "/reader", icon: BookOpen, label: "reader" },
  { to: "/notes", icon: NotebookPen, label: "notes" },
  { to: "/matrix", icon: Table2, label: "matrix" },
];
const bottomNav: NavItem[] = [
  { to: "/export", icon: FileOutput, label: "export" },
  { to: "/jobs", icon: ListChecks, label: "jobs" },
  { to: "/settings", icon: Settings, label: "settings" },
];

export function AppShell() {
  useJobEvents();
  useOpenRequests();
  const { sidebarOpen, inspectorOpen, focus } = useLayoutStore();
  const { pathname } = useLocation();
  // Focus mode belongs to the reader; another screen always has its shell.
  const focused = focus && pathname.startsWith("/reader");
  // The reader has its own left panel (outline, pages).
  const hasSidebar = !pathname.startsWith("/reader");
  const settingsRoute = pathname.startsWith("/settings");

  return (
    <TooltipProvider delayDuration={300}>
      <PreferencesSync />
      <PdfDrop />
      <ShortcutOverlay />
      <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)_auto] bg-canvas text-fg">
        {focused ? <div /> : <TopBar />}
        <div className="flex min-h-0">
          {!focused && <NavRail />}
          {sidebarOpen && hasSidebar && (
            <aside className="w-sidebar shrink-0 overflow-y-auto border-r border-line bg-surface">
              {settingsRoute ? (
                <SettingsNav />
              ) : pathname.startsWith("/library") ? (
                <LibrarySidebar />
              ) : pathname.startsWith("/notes") ? (
                <NotesSidebar />
              ) : (
                <SidebarPlaceholder />
              )}
            </aside>
          )}
          <main className="min-w-0 flex-1 overflow-y-auto">
            <Outlet />
          </main>
          {/* Screening has its own right-hand panel: the criteria. */}
          {inspectorOpen && !focused && !settingsRoute && !pathname.startsWith("/screening") && (
            <Inspector route={pathname} />
          )}
        </div>
        {!focused && <StatusBar />}
      </div>
    </TooltipProvider>
  );
}

function TopBar() {
  const { t } = useTranslation();
  const { toggleSidebar, toggleInspector } = useLayoutStore();
  const settings = useSettings();
  const update = useUpdateSettings();
  const dark = resolveTheme(settings.data?.theme ?? cachedTheme()) === "dark";

  return (
    <header className="flex h-10 items-center gap-2 border-b border-line bg-surface px-2">
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("shell.toggleSidebar")}
        onClick={toggleSidebar}
      >
        <PanelLeft />
      </Button>
      <span className="text-h3 text-fg">{t("app.name")}</span>
      <ReviewPicker />
      <div className="flex-1" />
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("shell.toggleTheme")}
        disabled={!settings.data || update.isPending}
        onClick={() => {
          update.mutate({ theme: dark ? "light" : "dark" });
        }}
      >
        {dark ? <Sun /> : <Moon />}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("shell.toggleInspector")}
        onClick={toggleInspector}
      >
        <PanelRight />
      </Button>
    </header>
  );
}

// The main screens answer to $mod+1 … $mod+7, in rail order.
const goToKeys = shortcut("global", "goTo").keys;

function NavRail() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  useShortcuts("global", {
    goTo: (event) => {
      const item = mainNav[Number.parseInt(event.key, 10) - 1];
      if (item) void navigate(item.to);
    },
  });
  const link = ({ to, icon: Icon, label }: NavItem, index: number, items: NavItem[]) => {
    const key = items === mainNav ? goToKeys[index] : undefined;
    const name = t(`nav.${label}`);
    return (
      <Tooltip key={to} label={key ? `${name} (${bindingLabel(key)})` : name}>
        <NavLink
          to={to}
          aria-label={t(`nav.${label}`)}
          className={({ isActive }) =>
            cn(
              "grid size-10 place-items-center rounded-md text-fg-muted hover:bg-hovered hover:text-fg [&_svg]:size-4",
              isActive && "bg-primary-soft text-primary",
            )
          }
        >
          <Icon aria-hidden />
        </NavLink>
      </Tooltip>
    );
  };

  return (
    <nav
      aria-label={t("nav.label")}
      className="flex w-rail shrink-0 flex-col items-center gap-1 border-r border-line bg-surface py-2"
    >
      {mainNav.map(link)}
      <div className="flex-1" />
      {bottomNav.map(link)}
    </nav>
  );
}

function SidebarPlaceholder() {
  const { t } = useTranslation();
  return <p className="p-4 text-meta text-fg-muted">{t("shell.sidebarPlaceholder")}</p>;
}

function Inspector({ route }: { route: string }) {
  const { t } = useTranslation();
  return (
    <aside
      aria-label={t("shell.inspectorTitle")}
      className="w-inspector shrink-0 overflow-y-auto border-l border-line bg-raised p-4"
    >
      {route.startsWith("/search") ? (
        <SearchInspector />
      ) : route.startsWith("/library") ? (
        <LibraryInspector />
      ) : route.startsWith("/reader") ? (
        <ReaderInspector />
      ) : route.startsWith("/notes") ? (
        <NotesInspector />
      ) : (
        <>
          <h2 className="mb-2 text-h3">{t("shell.inspectorTitle")}</h2>
          <p className="text-meta text-fg-muted">{t("shell.inspectorEmpty")}</p>
        </>
      )}
    </aside>
  );
}
