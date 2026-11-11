import { tagColors } from "./api";

/** A tag's colour as a design-token variable; muted for no or an unknown colour. */
export function tagColorVar(color: string | null): string {
  return color && (tagColors as readonly string[]).includes(color)
    ? `var(--color-highlight-${color})`
    : "var(--color-text-muted)";
}
