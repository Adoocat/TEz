// `pnpm bootstrap`: install every dependency and the git hooks. Safe to run again.
import { run } from "./lib/run.mjs";

const steps = [
  ["Python dependencies", "uv", ["sync", "--project", "backend"]],
  ["Node dependencies", "pnpm", ["install"]],
  ["git hooks", "uv", ["run", "--project", "backend", "pre-commit", "install"]],
];

for (const [title, cmd, args] of steps) {
  console.log(`\n== ${title}`);
  if (run(cmd, args) !== 0) {
    console.error(`\nbootstrap failed at: ${title}`);
    process.exit(1);
  }
}
console.log("\nbootstrap done. Next: pnpm dev, or pnpm check.");
