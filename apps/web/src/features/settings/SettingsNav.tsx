import { Archive, Info, Library, Network, SlidersHorizontal, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";

import { cn } from "@/lib/cn";

export const settingsSections = ["general", "sources", "library", "backup", "about"] as const;
export type SettingsSection = (typeof settingsSections)[number];

const icons: Record<SettingsSection, LucideIcon> = {
  general: SlidersHorizontal,
  sources: Network,
  library: Library,
  backup: Archive,
  about: Info,
};

export function SettingsNav() {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("settings.title")} className="p-2">
      <h2 className="px-2 pb-2 pt-1 text-h3">{t("settings.title")}</h2>
      {settingsSections.map((section) => {
        const Icon = icons[section];
        return (
          <NavLink
            key={section}
            to={`/settings/${section}`}
            className={({ isActive }) =>
              cn(
                "flex h-8 items-center gap-2 rounded-md px-2 text-ui text-fg hover:bg-hovered",
                isActive && "bg-primary-soft text-primary",
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {t(`settings.sections.${section}`)}
          </NavLink>
        );
      })}
    </nav>
  );
}
