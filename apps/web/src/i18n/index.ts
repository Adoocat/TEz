// react-i18next set-up. Every user-visible string is a key in locales/{tr,en}/common.json;
// the two files must have the same keys (checked by a test).
import i18next, { type TFunction } from "i18next";
import { initReactI18next } from "react-i18next";

import en from "../../locales/en/common.json";
import tr from "../../locales/tr/common.json";

export const languages = ["tr", "en"] as const;
export type Language = (typeof languages)[number];

export const resources = { tr: { common: tr }, en: { common: en } } as const;

/** The operating system's language if TEz has it, else English. */
export function systemLanguage(): Language {
  const preferred = typeof navigator === "undefined" ? [] : navigator.languages;
  return preferred.some((tag) => tag.toLowerCase().startsWith("tr")) ? "tr" : "en";
}

export function createI18n(language: Language) {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: "en",
    defaultNS: "common",
    interpolation: { escapeValue: false }, // React escapes already
    initAsync: false,
  });
  return instance;
}

/** Translate a backend error code (`{code, params}`) into a message. */
export function errorMessage(
  t: TFunction,
  error: { code: string; params?: Record<string, unknown> | null },
): string {
  return t(`errors.${error.code}`, { ...error.params, defaultValue: t("errors.unknown") });
}
