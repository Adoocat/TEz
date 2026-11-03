// Language and theme. The library's settings (GET/PATCH /settings) are the source of truth,
// so a choice survives restarts and works the same in the browser and in Tauri. A copy in
// localStorage lets the first paint use the right theme and language before the API answers.
import { languages, systemLanguage, type Language } from "@/i18n";

export type ThemePreference = "light" | "dark" | "system";
export type LanguagePreference = Language | null; // null: follow the operating system

const THEME_KEY = "tez.theme";
const LANGUAGE_KEY = "tez.language";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage disabled: fall back to defaults
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Storage disabled: the server copy still persists the choice.
  }
}

export function cachedTheme(): ThemePreference {
  const value = read(THEME_KEY);
  return value === "light" || value === "dark" ? value : "system";
}

export function cachedLanguage(): LanguagePreference {
  const value = read(LANGUAGE_KEY);
  return languages.find((l) => l === value) ?? null;
}

export function resolveLanguage(preference: LanguagePreference): Language {
  return preference ?? systemLanguage();
}

function prefersDark(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveTheme(preference: ThemePreference): "light" | "dark" {
  return preference === "dark" || (preference === "system" && prefersDark()) ? "dark" : "light";
}

/** Set `data-theme` on <html>; tokens.css switches every color variable on it. */
export function applyTheme(preference: ThemePreference): void {
  document.documentElement.dataset.theme = resolveTheme(preference);
  write(THEME_KEY, preference === "system" ? null : preference);
}

export function applyLanguage(preference: LanguagePreference): Language {
  const language = resolveLanguage(preference);
  document.documentElement.lang = language;
  write(LANGUAGE_KEY, preference);
  return language;
}

/** Re-apply a "system" theme when the operating system switches between light and dark. */
export function watchSystemTheme(onChange: () => void): () => void {
  if (typeof matchMedia !== "function") return () => undefined;
  const query = matchMedia("(prefers-color-scheme: dark)");
  query.addEventListener("change", onChange);
  return () => {
    query.removeEventListener("change", onChange);
  };
}
