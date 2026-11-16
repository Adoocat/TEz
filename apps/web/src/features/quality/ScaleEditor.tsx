// A question's answer scale: labels and optional scores, started from a preset or by hand.
import { Plus, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import type { Language, ScaleOption, ScalePresetView } from "./api";

export const minOptions = 2;
export const maxOptions = 12;

export function uiLanguage(language: string): Language {
  return language.startsWith("tr") ? "tr" : "en";
}

export function presetOptions(preset: ScalePresetView, language: Language): ScaleOption[] {
  return preset.options.map((option) => ({
    value: option.value,
    label: option.labels[language] ?? option.value,
    score: option.score,
  }));
}

/** A value no option uses yet; existing values never change, so answers keep pointing. */
function freshValue(options: ScaleOption[]): string {
  const taken = new Set(options.map((option) => option.value));
  let n = options.length + 1;
  while (taken.has(`o${String(n)}`)) n += 1;
  return `o${String(n)}`;
}

export function scaleIsValid(options: ScaleOption[]): boolean {
  return (
    options.length >= minOptions &&
    options.length <= maxOptions &&
    options.every((option) => option.label.trim() !== "")
  );
}

export function ScaleEditor({
  options,
  onChange,
}: {
  options: ScaleOption[];
  onChange: (options: ScaleOption[]) => void;
}) {
  const { t } = useTranslation();

  function update(index: number, change: Partial<ScaleOption>) {
    onChange(options.map((option, i) => (i === index ? { ...option, ...change } : option)));
  }

  return (
    <div className="space-y-1.5">
      <ol className="space-y-1">
        {options.map((option, index) => {
          const n = index + 1;
          return (
            <li key={option.value} className="flex items-center gap-1.5">
              <Input
                aria-label={t("quality.scale.label", { n })}
                value={option.label}
                maxLength={80}
                onChange={(event) => {
                  update(index, { label: event.target.value });
                }}
              />
              <Input
                aria-label={t("quality.scale.score", { n })}
                className="w-20"
                type="number"
                step="any"
                placeholder="—"
                value={option.score ?? ""}
                onChange={(event) => {
                  const raw = event.target.value;
                  update(index, { score: raw === "" ? null : Number(raw) });
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={t("quality.scale.remove", { n })}
                disabled={options.length <= minOptions}
                onClick={() => {
                  onChange(options.filter((_, i) => i !== index));
                }}
              >
                <X />
              </Button>
            </li>
          );
        })}
      </ol>
      <div className="flex items-center gap-3">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={options.length >= maxOptions}
          onClick={() => {
            onChange([...options, { value: freshValue(options), label: "", score: null }]);
          }}
        >
          <Plus />
          {t("quality.scale.add")}
        </Button>
        <span className="text-meta text-fg-muted">{t("quality.scale.scoreHint")}</span>
      </div>
    </div>
  );
}
