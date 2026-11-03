import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/**
 * Run a command with inherited stdio and return its exit code.
 * `shell` is needed on Windows to resolve `pnpm.cmd`; arguments here are fixed strings.
 */
export function run(cmd, args, cwd = root) {
  const result = spawnSync(cmd, args, { cwd, stdio: "inherit", shell: true });
  if (result.error) {
    console.error(`${cmd}: ${result.error.message}`);
    return 1;
  }
  return result.status ?? 1;
}
