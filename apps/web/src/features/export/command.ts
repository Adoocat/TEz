// "Copy terminal command" (Task 40): the `tez export` call that writes the same file. Only
// what the command can do: BibTeX or RIS of a review (all its papers or its included
// studies), a collection or the whole library. Chosen papers and formatted bibliographies
// have no command yet.
export type CommandScope =
  | { kind: "review"; title: string; included: boolean }
  | { kind: "collection"; name: string }
  | { kind: "library" };

/** Double-quoted when needed; works in PowerShell, cmd and POSIX shells for plain names. */
function quote(value: string): string {
  return /^[\p{L}\p{N}._/-]+$/u.test(value) ? value : `"${value.replace(/(["\\$`])/g, "\\$1")}"`;
}

export function exportCommand(
  format: "bibtex" | "ris",
  scope: CommandScope,
  fileName: string,
): string {
  const parts = ["tez", "export", "--format", format];
  if (scope.kind === "review") {
    parts.push("--review", quote(scope.title));
    if (scope.included) parts.push("--included");
  } else if (scope.kind === "collection") {
    parts.push("--collection", quote(scope.name));
  }
  parts.push("--output", quote(fileName));
  return parts.join(" ");
}
