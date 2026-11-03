// Desktop mode. The Rust shell starts the backend (apps/desktop/src-tauri/src/backend.rs),
// passes it a token over stdin and reports its state. The state may change before this
// code subscribes, so subscribe first, then ask for the current state (ADR 0001).
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import type { BackendError, BackendState, Platform } from "./types";

type ShellStatus =
  | { status: "starting" }
  | { status: "ready"; port: number; token: string }
  | { status: "failed"; code: string; params: Record<string, unknown> };

export function fromShell(status: ShellStatus): BackendState {
  switch (status.status) {
    case "starting":
      return { status: "starting" };
    case "ready":
      return {
        status: "ready",
        connection: { baseUrl: `http://127.0.0.1:${String(status.port)}`, token: status.token },
      };
    case "failed": {
      const error: BackendError = { code: status.code, params: status.params };
      return { status: "failed", error };
    }
  }
}

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export const tauriPlatform: Platform = {
  kind: "tauri",
  connectBackend(onChange) {
    let active = true;
    const unlisten = listen<ShellStatus>("backend-status", (event) => {
      if (active) onChange(fromShell(event.payload));
    });
    void unlisten.then(async () => {
      const current = await invoke<ShellStatus>("backend_status");
      if (active) onChange(fromShell(current));
    });
    return () => {
      active = false;
      void unlisten.then((stop) => {
        stop();
      });
    };
  },
};
