// Starts `tez-backend serve` on a new, empty library for the whole run, and stops it after.
// The address and token reach the tests through environment variables.
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const API_PORT = 8799;
const WEB_ORIGIN = "http://localhost:1431";
const root = path.resolve(import.meta.dirname, "../../..");

function stop(child: ChildProcess) {
  if (child.pid === undefined || child.exitCode !== null) return;
  if (process.platform === "win32") {
    // uv starts Python as a child; only a tree kill reaches it (and the worker under it).
    spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}

function waitForToken(child: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    let output = "";
    const timer = setTimeout(() => {
      reject(new Error(`backend did not start in time:\n${output}`));
    }, 90_000);
    const read = (chunk: Buffer) => {
      output += chunk.toString();
      const match = /token: (\S+)/.exec(output);
      if (match?.[1]) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    };
    child.stdout?.on("data", read);
    child.stderr?.on("data", read);
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`backend exited (${String(code)}):\n${output}`));
    });
  });
}

async function waitForHealth(api: string, token: string) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`${api}/health`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.ok) return;
    } catch {
      // not listening yet
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("backend never became healthy");
}

export default async function globalSetup() {
  const folder = mkdtempSync(path.join(tmpdir(), "tez-e2e-"));
  const library = path.join(folder, "library");
  const child = spawn(
    "uv",
    [
      "run",
      "--project",
      "backend",
      "tez-backend",
      "serve",
      "--library",
      library,
      "--create",
      "--port",
      String(API_PORT),
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        TEZ_CORS_ORIGINS: JSON.stringify([WEB_ORIGIN]),
        TEZ_LOG_FORMAT: "console",
      },
    },
  );
  const api = `http://127.0.0.1:${String(API_PORT)}`;
  const token = await waitForToken(child);
  await waitForHealth(api, token);
  process.env.TEZ_E2E_API = api;
  process.env.TEZ_E2E_TOKEN = token;

  return () => {
    stop(child);
    try {
      rmSync(folder, { recursive: true, force: true });
    } catch {
      // Windows may still hold the database for a moment; the OS cleans its temp folder.
    }
  };
}
