import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { openPdf, scrollBenchmark, type Viewer } from "./pdf";

type BackendInfo = { port: number; token: string; pid: number };
type Forwarded = { source: string; args: string[]; cwd: string };

const $ = (id: string) => document.getElementById(id)!;
const errors: string[] = [];
function reportError(where: string, err: unknown) {
  errors.push(`${where}: ${err instanceof Error ? `${err.name}: ${err.message}` : String(err)}`);
  void invoke("report", { key: "frontend_errors", value: errors });
}
window.addEventListener("error", (e) => reportError("error", e.error ?? e.message));
window.addEventListener("unhandledrejection", (e) => reportError("unhandledrejection", e.reason));
const timings: Record<string, number> = {};
let backend: BackendInfo | null = null;
let viewer: Viewer | null = null;

function showTimings() {
  $("timings").textContent = Object.entries(timings)
    .map(([k, v]) => `${k.padEnd(18)} ${v.toFixed(0)} ms`)
    .join("\n");
}

async function mark(name: string) {
  timings[name] = await invoke<number>("mark", { name });
  showTimings();
}

function addForwarded(f: Forwarded) {
  const li = document.createElement("li");
  li.textContent = `[${f.source}] ${f.args.join(" ") || "(argümansız)"}${f.cwd ? `  · cwd=${f.cwd}` : ""}`;
  $("forwarded").appendChild(li);
}

async function onBackend(info: BackendInfo) {
  if (backend) return;
  backend = info;
  $("backend").textContent = `backend: 127.0.0.1:${info.port} · pid ${info.pid}`;
  const unauth = await fetch(`http://127.0.0.1:${info.port}/health`);
  const res = await fetch(`http://127.0.0.1:${info.port}/health`, {
    headers: { Authorization: `Bearer ${info.token}` },
  });
  await mark("first_health_ms");
  const health = await res.json();
  await invoke("report", { key: "health", value: { ...health, unauthorized_status: unauth.status } });
  $("backend").textContent += ` · /health ${res.status} · tokensız ${unauth.status}`;
  if (selftest) void runPdfTest();
}

async function runPdfTest() {
  if (!backend || viewer) return;
  ($("pdf-btn") as HTMLButtonElement).disabled = true;
  viewer = await openPdf($("viewer"), `http://127.0.0.1:${backend.port}/files/sample.pdf`, backend.token);
  $("pdf-stats").textContent = JSON.stringify(viewer.stats, null, 2);
  await invoke("report", { key: "pdf_open", value: viewer.stats });
  ($("bench-btn") as HTMLButtonElement).disabled = false;
  if (selftest) await runBenchmark();
}

async function runBenchmark() {
  if (!viewer) return;
  ($("bench-btn") as HTMLButtonElement).disabled = true;
  const result = await scrollBenchmark(viewer);
  $("pdf-stats").textContent = JSON.stringify({ ...viewer.stats, ...result }, null, 2);
  await invoke("report", { key: "pdf_bench", value: result });
  await mark("selftest_done_ms");
  ($("bench-btn") as HTMLButtonElement).disabled = false;
}

const initial = await invoke<string[]>("initial_args");
const selftest = initial.includes("--selftest");
addForwarded({ source: "first-launch", args: initial, cwd: "" });

$("pdf-btn").addEventListener("click", () => void runPdfTest());
$("bench-btn").addEventListener("click", () => void runBenchmark());

await listen<BackendInfo>("backend-ready", (e) => {
  void invoke("mark", { name: "frontend_got_backend_ready_ms" });
  onBackend(e.payload).catch((err) => reportError("onBackend", err));
});
await listen<Forwarded>("forwarded", (e) => addForwarded(e.payload));
await listen<number | null>("backend-exited", (e) => {
  $("backend").textContent = `backend: sonlandı (kod ${e.payload})`;
});

requestAnimationFrame(() => requestAnimationFrame(() => void mark("window_ready_ms")));

const info = await invoke<BackendInfo | null>("backend_info");
if (info) onBackend(info).catch((err) => reportError("onBackend", err));
