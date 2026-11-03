// Placeholder for root scripts whose task has not landed yet, so every documented command runs.
const [name, task] = process.argv.slice(2);
const when = task ? `Task ${task}` : "a later task";
console.log(`pnpm ${name}: not set up yet (arrives in ${when}; see docs/progress.md).`);
