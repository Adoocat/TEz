// Applies the stored language and theme to the whole app whenever the settings change.
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { applyLanguage, applyTheme, watchSystemTheme } from "@/lib/preferences";

import { useSettings } from "./api";

export function PreferencesSync() {
  const { data } = useSettings();
  const { i18n } = useTranslation();

  const theme = data?.theme;
  const language = data?.language;

  useEffect(() => {
    if (theme === undefined) return;
    applyTheme(theme);
    if (theme !== "system") return;
    return watchSystemTheme(() => {
      applyTheme("system");
    });
  }, [theme]);

  useEffect(() => {
    if (language === undefined) return;
    void i18n.changeLanguage(applyLanguage(language));
  }, [language, i18n]);

  return null;
}
