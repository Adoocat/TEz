// The only place that knows whether TEz runs in Tauri or in a browser (CLAUDE.md).
import { browserPlatform } from "./browser";
import { isTauri, tauriPlatform } from "./tauri";
import type { Platform } from "./types";

export type { BackendConnection, BackendError, BackendState, OpenRequest, Platform } from "./types";

export function detectPlatform(): Platform {
  return isTauri() ? tauriPlatform : browserPlatform;
}
