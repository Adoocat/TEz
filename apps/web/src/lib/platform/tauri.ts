// Desktop mode. The Rust shell starts the backend (apps/desktop/src-tauri/src/backend.rs),
// passes it a token over stdin and reports its state. The state may change before this
// code subscribes, so subscribe first, then ask for the current state (ADR 0001).
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

import type { BackendError, BackendState, OpenRequest, Platform } from "./types";

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
  onOpenRequests(handle) {
    // The event is only a nudge: requests are taken from the shell's queue, so those from
    // start-up and those from a later `tez <file>` arrive the same way, and none twice.
    // Taken requests are always handled, even if this subscription has just been undone: the
    // queue no longer holds them, so dropping them would lose them (React StrictMode
    // subscribes, unsubscribes and subscribes again on start-up).
    const take = async () => {
      const requests = await invoke<OpenRequest[]>("take_open_requests");
      if (requests.length > 0) handle(requests);
    };
    const unlisten = listen("open-requests", () => {
      void take();
    });
    void unlisten.then(take);
    return () => {
      void unlisten.then((stop) => {
        stop();
      });
    };
  },
};
