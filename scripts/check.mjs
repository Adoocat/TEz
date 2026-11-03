// `pnpm check`: lint, type check and test every part of the repo; the same steps run in CI.
// Runs all steps even after a failure so one run shows every problem, then exits 1 if any failed.
//
//   pnpm check            all steps
//   pnpm check py web     only the named groups (py, api, web, rust, format)
import path from "node:path";

import { root, run } from "./lib/run.mjs";

const backend = path.join(root, "backend");
const cargoToml = path.join("apps", "desktop", "src-tauri", "Cargo.toml");
const uv = (...args) => ["uv", ["run", "--project", "backend", ...args]];

const steps = [
  ["py", "ruff lint", ...uv("ruff", "check", "backend")],
  ["py", "ruff format", ...uv("ruff", "format", "--check", "backend")],
  ["py", "pyright", "pnpm", ["exec", "pyright", "-p", "backend"]],
  ["py", "pytest", "uv", ["run", "pytest"], backend],
  // The generated TypeScript client must match the backend's OpenAPI schema.
  ["api", "client up to date", "node", ["scripts/gen-api.mjs", "--check"]],
  ["web", "eslint", "pnpm", ["--filter", "@tez/web", "lint"]],
  ["web", "tsc", "pnpm", ["--filter", "@tez/web", "typecheck"]],
  ["web", "vitest", "pnpm", ["--filter", "@tez/web", "test"]],
  ["format", "prettier", "pnpm", ["exec", "prettier", "--check", "."]],
  ["rust", "cargo fmt", "cargo", ["fmt", "--check", "--manifest-path", cargoToml]],
  [
    "rust",
    "cargo clippy",
    "cargo",
    ["clippy", "--quiet", "--manifest-path", cargoToml, "--", "-D", "warnings"],
  ],
];

const groups = process.argv.slice(2);
const unknown = groups.filter((g) => !steps.some(([group]) => group === g));
if (unknown.length > 0) {
  console.error(`unknown group(s): ${unknown.join(", ")}; use py, api, web, rust, format`);
  process.exit(2);
}

const results = [];
for (const [group, title, cmd, args, cwd] of steps) {
  if (groups.length > 0 && !groups.includes(group)) continue;
  console.log(`\n== [${group}] ${title}`);
  const started = Date.now();
  const ok = run(cmd, args, cwd) === 0;
  results.push({ title: `[${group}] ${title}`, ok, seconds: (Date.now() - started) / 1000 });
}

console.log("\n== summary");
for (const { title, ok, seconds } of results) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${title}  (${seconds.toFixed(1)} s)`);
}
const failed = results.filter((r) => !r.ok).length;
console.log(failed === 0 ? "\npnpm check: all green" : `\npnpm check: ${failed} step(s) failed`);
process.exit(failed === 0 ? 0 : 1);
