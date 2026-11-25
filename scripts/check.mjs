// `pnpm check`: lint, type check and test every part of the repo; the same steps run in CI.
// Runs all steps even after a failure so one run shows every problem, then exits 1 if any failed.
//
//   pnpm check            all steps
//   pnpm check py web     only the named groups (py, api, web, rust, format)
//
// The groups run side by side (the steps inside a group one after another), and the backend
// tests run on every core (pytest-xdist). A step's output is printed only when it fails, so a
// green run stays short.
import { spawn } from "node:child_process";
import path from "node:path";

import { root } from "./lib/run.mjs";

const backend = path.join(root, "backend");
const cargoToml = path.join("apps", "desktop", "src-tauri", "Cargo.toml");
const uv = (...args) => ["uv", ["run", "--project", "backend", ...args]];

const steps = [
  ["py", "ruff lint", ...uv("ruff", "check", "backend")],
  ["py", "ruff format", ...uv("ruff", "format", "--check", "backend")],
  ["py", "pyright", "pnpm", ["exec", "pyright", "-p", "backend"]],
  ["py", "pytest", "uv", ["run", "pytest", "-n", "auto", "-m", '"not timing"'], backend],
  // Tests that measure how long something takes run alone, not beside eleven others.
  ["py", "pytest (timing)", "uv", ["run", "pytest", "-m", "timing"], backend],
  // The generated TypeScript client must match the backend's OpenAPI schema.
  ["api", "client up to date", "node", ["scripts/gen-api.mjs", "--check"]],
  // The CSS variables must match docs/design/tokens.json.
  ["web", "tokens up to date", "node", ["scripts/gen-tokens.mjs", "--check"]],
  ["web", "eslint", "pnpm", ["--filter", "@tez/web", "lint"]],
  ["web", "tsc", "pnpm", ["--filter", "@tez/web", "typecheck"]],
  ["web", "vitest", "pnpm", ["--filter", "@tez/web", "test"]],
  ["format", "prettier", "pnpm", ["exec", "prettier", "--check", "."]],
  ["rust", "cargo fmt", "cargo", ["fmt", "--check", "--manifest-path", cargoToml]],
  ["rust", "cargo test", "cargo", ["test", "--quiet", "--manifest-path", cargoToml]],
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

/** Run a command, keeping its output to show only if it fails. */
function runQuiet(cmd, args, cwd = root) {
  return new Promise((resolve) => {
    const chunks = [];
    // `shell` resolves `pnpm.cmd` on Windows; the arguments are fixed strings.
    const child = spawn(cmd, args, { cwd, shell: true, env: { ...process.env, FORCE_COLOR: "0" } });
    child.stdout.on("data", (chunk) => chunks.push(chunk));
    child.stderr.on("data", (chunk) => chunks.push(chunk));
    child.on("error", (error) => {
      chunks.push(Buffer.from(`${cmd}: ${error.message}\n`));
      resolve({ code: 1, output: Buffer.concat(chunks).toString() });
    });
    child.on("close", (code) => {
      resolve({ code: code ?? 1, output: Buffer.concat(chunks).toString() });
    });
  });
}

const chosen = steps.filter(([group]) => groups.length === 0 || groups.includes(group));
const lanes = [...new Set(chosen.map(([group]) => group))];
const startedAll = Date.now();
const results = [];

await Promise.all(
  lanes.map(async (lane) => {
    for (const [group, title, cmd, args, cwd] of chosen.filter(([g]) => g === lane)) {
      const started = Date.now();
      const { code, output } = await runQuiet(cmd, args, cwd);
      const seconds = (Date.now() - started) / 1000;
      const result = { title: `[${group}] ${title}`, ok: code === 0, seconds };
      results.push(result);
      console.log(`${result.ok ? "PASS" : "FAIL"}  ${result.title}  (${seconds.toFixed(1)} s)`);
      if (!result.ok) console.log(`\n== ${result.title} output\n${output.trimEnd()}\n`);
    }
  }),
);

const failed = results.filter((r) => !r.ok);
const total = ((Date.now() - startedAll) / 1000).toFixed(1);
if (failed.length > 0) {
  console.log("\n== failed");
  for (const { title } of failed) console.log(`FAIL  ${title}`);
}
console.log(
  failed.length === 0
    ? `\npnpm check: all green in ${total} s`
    : `\npnpm check: ${String(failed.length)} step(s) failed (${total} s)`,
);
process.exit(failed.length === 0 ? 0 : 1);
