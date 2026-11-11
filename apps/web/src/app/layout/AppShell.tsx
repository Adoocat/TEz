// The shell every screen shares (design-prompt §3): top bar, navigation rail, context
// sidebar, main area, optional inspector, status bar.
import {
  BookOpen,
  FileCheck2,
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
import { NavLink, Outlet, useLocation } from "react-router";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { PdfDrop } from "@/features/files/PdfDrop";
import { useJobEvents } from "@/features/jobs/useJobEvents";
import { LibraryInspector } from "@/features/library/LibraryInspector";
import { LibrarySidebar } from "@/features/library/LibrarySidebar";
import { ReviewPicker } from "@/features/reviews/ReviewPicker";
import { SearchInspector } from "@/features/search/SearchInspector";
import { useSettings, useUpdateSettings } from "@/features/settings/api";
import { SettingsNav } from "@/features/settings/SettingsNav";
import { PreferencesSync } from "@/features/settings/PreferencesSync";
import { cn } from "@/lib/cn";
import { cachedTheme, resolveTheme } from "@/lib/preferences";

import { StatusBar } from "./StatusBar";
import { useLayoutStore } from "./uiStore";

interface NavItem {
  to: string;
  icon: LucideIcon;
  label: "search" | "library" | "screening" | "reader" | "notes" | "matrix" | "jobs" | "settings";
}

const mainNav: NavItem[] = [
  { to: "/search", icon: Search, label: "search" },
  { to: "/library", icon: Library, label: "library" },
  { to: "/screening", icon: FileCheck2, label: "screening" },
  { to: "/reader", icon: BookOpen, label: "reader" },
  { to: "/notes", icon: NotebookPen, label: "notes" },
  { to: "/matrix", icon: Table2, label: "matrix" },
];
const bottomNav: NavItem[] = [
  { to: "/jobs", icon: ListChecks, label: "jobs" },
  { to: "/settings", icon: Settings, label: "settings" },
];

export function AppShell() {
  useJobEvents();
  const { sidebarOpen, inspectorOpen } = useLayoutStore();
  const { pathname } = useLocation();
  const settingsRoute = pathname.startsWith("/settings");

  return (
    <TooltipProvider delayDuration={300}>
      <PreferencesSync />
      <PdfDrop />
      <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)_auto] bg-canvas text-fg">
        <TopBar />
        <div className="flex min-h-0">
          <NavRail />
          {sidebarOpen && (
            <aside className="w-sidebar shrink-0 overflow-y-auto border-r border-line bg-surface">
              {settingsRoute ? (
                <SettingsNav />
              ) : pathname.startsWith("/library") ? (
                <LibrarySidebar />
              ) : (
                <SidebarPlaceholder />
              )}
            </aside>
          )}
          <main className="min-w-0 flex-1 overflow-y-auto">
            <Outlet />
          </main>
          {inspectorOpen && !settingsRoute && <Inspector route={pathname} />}
        </div>
        <StatusBar />
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

function NavRail() {
  const { t } = useTranslation();
  const link = ({ to, icon: Icon, label }: NavItem) => (
    <Tooltip key={to} label={t(`nav.${label}`)}>
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
      ) : (
        <>
          <h2 className="mb-2 text-h3">{t("shell.inspectorTitle")}</h2>
          <p className="text-meta text-fg-muted">{t("shell.inspectorEmpty")}</p>
        </>
      )}
    </aside>
  );
}
